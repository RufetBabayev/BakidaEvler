"""bina.az toplayıcısı (Bakı, satış).

HTML-dən yox, saytın öz daxili GraphQL ünvanından (https://bina.az/graphql) istifadə edir:
brauzerdə sayt da eyni sorğuları göndərir. Giriş (login) və ya captcha tələb olunmur.

Hər scraper eyni interfeysi verir:
    SOURCE: str
    fetch(known_ids, min_new_id, reveal_phone, max_pages, log) -> (elanlar, xetalar)
"""
import random
import time
from datetime import datetime, timedelta, timezone

import requests

SOURCE = "bina.az"
BASE = "https://bina.az"
GRAPHQL = BASE + "/graphql"
TZ = timezone(timedelta(hours=4))  # Bakı vaxtı

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PAGE_SIZE = 25          # saytın icazə verdiyi maksimum
DELAY = (2.0, 4.0)      # sorğular arası təsadüfi fasilə (saniyə)

# Bakı = cityId 1. Kateqoriyalar: 1 = Mənzil (yeni+köhnə tikili), 5 = Həyət evi/Bağ evi.
# Səhifə büdcəsi (cəmi 3): mənzil 2 səhifə, həyət evi 1 səhifə.
PLAN = [("1", 2), ("5", 1)]

LIST_QUERY = """
query SearchItems($first: Int, $filter: ItemFilter, $sort: ItemConnectionSort!, $cursor: String) {
  itemsConnection(first: $first, after: $cursor, filter: $filter, sort: $sort) {
    totalCount
    pageInfo { hasNextPage endCursor }
    edges { node { id path updatedAt } }
  }
}
"""

ITEM_QUERY = """
query CurrentItem($id: ID!) {
  item(id: $id) {
    id path state isLeased address description rooms floor floors updatedAt views
    area { value units }
    landArea { value units }
    price { total currency }
    photos { full }
    category { id name }
    city { name }
    location { fullName }
    hasBillOfSale hasMortgage hasRepair
    contactName contactTypeName
    phones { ... on MaskedPhone { value } ... on Phone { value } }
    nearestLocations { ... on Location { fullName } ... on City { name } }
  }
}
"""

REVEAL_MUTATION = """
mutation RevealPhones($targetId: ID!, $targetType: PhonesRevealTargetTypeEnum!, $source: PhonesRevealSourceEnum!) {
  revealPhones(input: {targetId: $targetId, targetType: $targetType, source: $source}) {
    phones
    errors { code message path }
  }
}
"""


HOME_CATEGORIES = {"1", "2", "3", "5"}  # mənzil (yeni/köhnə tikili), həyət evi/bağ evi
GAP_LIMIT = 8        # ardıcıl bu qədər boş ID gələndə "sona çatdıq" sayırıq
PENDING_WINDOW = 150  # boş çıxan ID-ni bu qədər ID müddətində yenidən yoxlayırıq (moderasiya gecikməsi)


class Bloklandi(Exception):
    """Sayt sorğunu rədd etdi (403/429/captcha). Davam etmirik."""


class _Client:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Origin": BASE,
            "Referer": BASE + "/baki/alqi-satqi/menziller",
            "X-Platform": "desktop",
        })
        self._first = True

    def gql(self, query, variables):
        if not self._first:
            time.sleep(random.uniform(*DELAY))
        self._first = False
        r = self.s.post(GRAPHQL, json={"query": query, "variables": variables}, timeout=25)
        if r.status_code in (403, 429) or "captcha" in r.text[:2000].lower():
            raise Bloklandi(f"HTTP {r.status_code}: sayt sorğunu qəbul etmədi")
        r.raise_for_status()
        data = r.json()
        if data.get("errors") and not data.get("data"):
            raise RuntimeError(data["errors"][0].get("message", "GraphQL xətası"))
        return data["data"]


def _now():
    return datetime.now(TZ).isoformat(timespec="seconds")


def _seller_type(label):
    """Saytın öz yazısını ('vasitəçi (agent)', 'mülkiyyətçi') iki dəyərə gətirir."""
    if not label:
        return None
    low = label.lower()
    if "vasitəçi" in low or "vasitəci" in low:
        return "vasitəçi"
    if "mülkiyyətçi" in low:
        return "mülkiyyətçi"
    return label


def _split_locations(item):
    rayon = qesebe = metro = None
    names = [x.get("fullName") for x in (item.get("nearestLocations") or []) if x.get("fullName")]
    if item.get("location") and item["location"].get("fullName"):
        names.append(item["location"]["fullName"])
    for n in names:
        low = n.lower().strip()
        if low.endswith(" m.") and not metro:
            metro = n
        elif low.endswith(" r.") and not rayon:
            rayon = n
        elif (low.endswith(" q.") or low.endswith(" qəs.")) and not qesebe:
            qesebe = n
    return rayon, qesebe, metro


def _normalize(it):
    area = it.get("area") or {}
    land = it.get("landArea") or {}
    price = it.get("price") or {}
    category = (it.get("category") or {}).get("name")
    rayon, qesebe, metro = _split_locations(it)
    phones = it.get("phones") or []
    area_m2 = area.get("value") if (area.get("units") or "").startswith("m") else None
    rooms = it.get("rooms")

    parts = []
    if rooms:
        parts.append(f"{rooms} otaqlı")
    if category:
        parts.append(category.lower())
    title = "Satılır " + " ".join(parts) if parts else "Satılır"
    if area_m2:
        title += f", {area_m2:g} m²"

    address = ", ".join(x for x in [(it.get("city") or {}).get("name"), rayon, qesebe, it.get("address")] if x)
    return {
        "mənbə": SOURCE,
        "elan_id": str(it["id"]),
        "link": BASE + (it.get("path") or f"/items/{it['id']}"),
        "başlıq": title,
        "qiymət": price.get("total"),
        "valyuta": price.get("currency"),
        "kateqoriya": category.lower() if category else None,
        "otaq_sayı": rooms,
        "sahə_m2": area_m2,
        "torpaq_sahəsi_sot": land.get("value") if (land.get("units") or "").lower().startswith("sot") else None,
        "mərtəbə": it.get("floor"),
        "ümumi_mərtəbə": it.get("floors"),
        "rayon": rayon,
        "qəsəbə": qesebe,
        "metro": metro,
        "ünvan": address or None,
        "təsvir": (it.get("description") or "").strip() or None,
        "şəkil_linkləri": [p["full"] for p in (it.get("photos") or []) if p.get("full")],
        "çıxarış_var": it.get("hasBillOfSale"),
        "təmir": "var" if it.get("hasRepair") else "yoxdur",
        "ipoteka": it.get("hasMortgage"),
        "satıcı_tipi": _seller_type(it.get("contactTypeName")),
        "satıcı_adı": it.get("contactName"),
        "telefon": phones[0].get("value") if phones else None,
        "satıcı_açar": ("tel:" + phones[0]["value"]) if phones and phones[0].get("value") else None,
        "paylaşılma_tarixi": None,  # bina.az bu məlumatı vermir
        "yenilənmə_tarixi": it.get("updatedAt"),
        "toplanma_vaxtı": _now(),
        "yeni": True,
    }


def fetch(known_ids, min_new_id=None, reveal_phone=False, max_pages=3, log=print):
    """Siyahıdakı elanları qaytarır.

    DİQQƏT: bina.az "ən yeni" sırası BUMP vaxtına görədir, yəni siyahıda köhnə elanlar da
    yenilənib yuxarı çıxır. Elan ID-ləri isə yaranma sırası ilə artır. Ona görə "yeni" =
    əvvəl görülməyib VƏ ID-si əvvəlki işləmədəki ən böyük ID-dən böyükdür
    (min_new_id=None olanda, yəni ilk işləmədə, hamısı yenidir).

    Yeni olmayan elanların detalına girmirik (saytı yükləməmək üçün): onlar yalnız
    {"elan_id", "link", "yenilənmə_tarixi", "yeni": False} olur, qalanını main.py keşdən doldurur.
    """
    client = _Client()
    results, errors = [], []
    pages_done = 0
    try:
        for category_id, pages in PLAN:
            cursor = None
            for _ in range(pages):
                if pages_done >= max_pages:
                    break
                data = client.gql(LIST_QUERY, {
                    "first": PAGE_SIZE,
                    "filter": {"cityId": "1", "categoryId": category_id, "leased": False},
                    "sort": "BUMPED_AT_DESC",
                    "cursor": cursor,
                })["itemsConnection"]
                pages_done += 1
                log(f"  siyahı: kateqoriya {category_id}, səhifə {pages_done}, {len(data['edges'])} elan")
                for edge in data["edges"]:
                    node = edge["node"]
                    item_id = str(node["id"])
                    if any(r["elan_id"] == item_id for r in results):
                        continue  # bumplanma səbəbindən səhifələr arası təkrar
                    is_new = item_id not in known_ids and (min_new_id is None or int(item_id) > min_new_id)
                    if not is_new:
                        results.append({"elan_id": item_id, "link": BASE + node["path"],
                                        "yenilənmə_tarixi": node.get("updatedAt"), "yeni": False})
                        continue
                    try:
                        detail = client.gql(ITEM_QUERY, {"id": item_id})["item"]
                        if not detail:
                            raise RuntimeError("elan tapılmadı")
                        rec = _normalize(detail)
                        if reveal_phone:
                            rev = client.gql(REVEAL_MUTATION, {"targetId": item_id, "targetType": "ITEM", "source": "DESKTOP"})
                            phones = (rev.get("revealPhones") or {}).get("phones") or []
                            if phones:
                                rec["telefon"] = phones[0]
                                rec["satıcı_açar"] = "tel:" + phones[0]
                        results.append(rec)
                    except Bloklandi:
                        raise
                    except Exception as e:  # tək elanın xətası hamısını dayandırmasın
                        errors.append(f"{item_id}: {e}")
                if not data["pageInfo"]["hasNextPage"]:
                    break
                cursor = data["pageInfo"]["endCursor"]
    except Bloklandi as e:
        errors.append(f"BLOKLANMA ƏLAMƏTİ: {e}. Dayandım.")
    except requests.RequestException as e:
        errors.append(f"şəbəkə xətası: {e}")
    return results, errors


def _wanted(detail):
    """Elan bizə lazımdır? (dərc olunub, satış, Bakı, ev kateqoriyası)"""
    return bool(
        detail
        and detail.get("state") == "PUBLISHED"
        and not detail.get("isLeased")
        and (detail.get("city") or {}).get("name") == "Bakı"
        and str((detail.get("category") or {}).get("id")) in HOME_CATEGORIES
    )


def fetch_incremental(last_id, pending, reveal_phone=False, max_requests=60, log=print):
    """last_id-dən yuxarı ID-ləri bir-bir yoxlayır (ID-lər yaranma sırası ilə artır).

    Bu, "bump" sırasındakı siyahıdan fərqli olaraq yeni elanları qaçırmır.
    pending: əvvəl boş çıxmış (silinmiş və ya moderasiyada) ID-lər; yenidən yoxlanılır.
    Qaytarır: (elanlar, xetalar, yeni_last_id, yeni_pending)
    """
    client = _Client()
    results, errors = [], []
    requests_made = 0
    max_seen = last_id
    new_pending = []

    def check(item_id):
        nonlocal requests_made
        requests_made += 1
        detail = client.gql(ITEM_QUERY, {"id": str(item_id)})["item"]
        if not detail:
            return None, False
        if not _wanted(detail):
            return None, True  # mövcuddur, amma bizə lazım deyil (kirayə, başqa şəhər...)
        rec = _normalize(detail)
        if reveal_phone:
            rev = client.gql(REVEAL_MUTATION, {"targetId": str(item_id), "targetType": "ITEM", "source": "DESKTOP"})
            phones = (rev.get("revealPhones") or {}).get("phones") or []
            if phones:
                rec["telefon"] = phones[0]
                rec["satıcı_açar"] = "tel:" + phones[0]
        return rec, True

    try:
        # 1) əvvəl boş çıxanları yenidən yoxla (moderasiyadan çıxmış ola bilər)
        for pid in sorted(pending):
            if requests_made >= max_requests // 3 or pid < last_id - PENDING_WINDOW:
                if pid >= last_id - PENDING_WINDOW:
                    new_pending.append(pid)
                continue
            try:
                rec, exists = check(pid)
            except Bloklandi:
                raise
            except Exception as e:
                errors.append(f"{pid}: {e}")
                new_pending.append(pid)
                continue
            if rec:
                results.append(rec)
            elif not exists:
                new_pending.append(pid)

        # 2) frontiera doğru irəlilə
        gap, cur = 0, last_id
        while gap < GAP_LIMIT and requests_made < max_requests:
            cur += 1
            try:
                rec, exists = check(cur)
            except Bloklandi:
                raise
            except Exception as e:
                errors.append(f"{cur}: {e}")
                break
            if exists:
                gap = 0
                max_seen = cur
                if rec:
                    results.append(rec)
            else:
                gap += 1
                new_pending.append(cur)
        # frontier boşluqlarını (sondakı GAP_LIMIT boş ID) yenidən saxlayırıq, max_seen-dən sonrakılar
        log(f"  ID skanı: {last_id + 1}..{cur}, {requests_made} sorğu, {len(results)} uyğun elan")
    except Bloklandi as e:
        errors.append(f"BLOKLANMA ƏLAMƏTİ: {e}. Dayandım.")
    except requests.RequestException as e:
        errors.append(f"şəbəkə xətası: {e}")
    return results, errors, max_seen, sorted(p for p in set(new_pending) if p < max_seen)
