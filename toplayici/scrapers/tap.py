"""tap.az toplayıcısı (Bakı, satış: mənzil + həyət evi/bağ evi).

tap.az də bina.az kimi daxili GraphQL (`POST https://tap.az/graphql`) işlədir. Login/captcha yoxdur.
Telefon sayt tərəfindən tam gizlədilir ("+994 •••"), ona görə satıcını elan sahibinin ID-si
(`satıcı_açar`) ilə tanıyırıq. Satıcı tipi: mağaza/agentlik hesabı = vasitəçi, şəxsi hesab = mülkiyyətçi
(saytın öz ayrımı, `isShop`).

Interfeys (list-əsaslı scraper):
    SOURCE: str
    fetch_latest(known_ids, min_new_id, reveal_phone, log) -> (elanlar, xetalar, max_id)
"""
from .common import Bloklandi, Client, now_iso, split_location, text_flags, to_float

import requests

SOURCE = "tap.az"
BASE = "https://tap.az"

BAKI = "Z2lkOi8vdGFwL1JlZ2lvbi80MjA"  # Region "Bakı"
# (kateqoriya id, "Elan növü" property id, "Satılır/Satış" option id, səhifə sayı)
PLAN = [
    ("Z2lkOi8vdGFwL0NhdGVnb3J5LzYzNQ", "740", "3722", 2),   # Mənzillər, Satılır
    ("Z2lkOi8vdGFwL0NhdGVnb3J5LzYwMQ", "750", "3869", 1),   # Həyət evləri/bağ evləri, Satış
]
PAGE = 24

LIST_QUERY = """
query($f: AdFilterInput, $after: String) {
  adSearch(source: DESKTOP, filters: $f) {
    ads(first: 24, after: $after) {
      nodes { legacyResourceId updatedAt }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

ITEM_QUERY = """
query($id: ID!) {
  adDetails(legacyId: $id, source: DESKTOP) {
    id title body price region path updatedAt legacyResourceId
    photos { url }
    contact { name phones type }
    shop { name }
    user { legacyId publishedAdsCount }
    azProperties { name value }
  }
}
"""


def _props(detail):
    out = {}
    for p in detail.get("azProperties") or []:
        name = (p.get("name") or "").strip().lower().replace("м", "m")  # kiril "м" -> latın
        out[name] = p.get("value")
    return out


def _normalize(d):
    props = _props(d)
    loc = props.get("yerləşmə yeri")
    rayon, qesebe, metro = split_location(loc)
    if loc and not (rayon or qesebe or metro):
        rayon = loc  # "Xətai" kimi sonluqsuz yazılıbsa rayon sayırıq
    kateqoriya = (props.get("binanın tipi") or props.get("əmlakın növü") or "").lower() or None
    otaq = to_float(props.get("otaq sayı"))
    sahe = to_float(props.get("sahə, m²") or props.get("sahə, m2"))
    shop = (d.get("shop") or {}).get("name")
    contact = d.get("contact") or {}
    user = d.get("user") or {}
    phones = [p for p in (contact.get("phones") or []) if p and sum(ch.isdigit() for ch in p) >= 9]  # "+994 •••" tam gizlidir
    cixaris, ipoteka, temir = text_flags(d.get("body"))

    tip = "vasitəçi" if shop else "mülkiyyətçi"
    title = d.get("title") or "Satılır"
    return {
        "mənbə": SOURCE,
        "elan_id": str(d["legacyResourceId"]),
        "link": BASE + d["path"],
        "başlıq": title,
        "qiymət": d.get("price"),
        "valyuta": "AZN",
        "kateqoriya": kateqoriya,
        "otaq_sayı": int(otaq) if otaq is not None else None,
        "sahə_m2": sahe,
        "torpaq_sahəsi_sot": None,
        "mərtəbə": None,
        "ümumi_mərtəbə": None,
        "rayon": rayon,
        "qəsəbə": qesebe,
        "metro": metro,
        "ünvan": ", ".join(x for x in [d.get("region"), loc] if x) or None,
        "təsvir": (d.get("body") or "").strip() or None,
        "şəkil_linkləri": [p["url"] for p in (d.get("photos") or []) if p.get("url")],
        "çıxarış_var": cixaris,
        "təmir": temir,
        "ipoteka": ipoteka,
        "satıcı_tipi": tip,
        "satıcı_adı": shop or contact.get("name"),
        "telefon": phones[0] if phones else None,
        "satıcı_açar": f"tap:{user['legacyId']}" if user.get("legacyId") else None,
        "satıcının_elan_sayı": user.get("publishedAdsCount"),
        "paylaşılma_tarixi": None,
        "yenilənmə_tarixi": d.get("updatedAt"),
        "toplanma_vaxtı": now_iso(),
        "yeni": True,
    }


def fetch_latest(known_ids, min_new_id=None, reveal_phone=False, log=print):
    """Ən son yenilənən elanları siyahıdan götürür; yalnız YENİ olanların detalına girir.

    Yeni = əvvəl görülməyib VƏ ID-si əvvəlki işləmənin ən böyük ID-sindən böyükdür
    (siyahı bump sırasındadır, köhnə elanlar da yuxarı çıxır). İlk işləmədə hamısı yenidir.
    """
    client = Client(BASE, {"Origin": BASE, "Referer": BASE + "/"})
    results, errors = [], []
    max_id = min_new_id or 0
    seen_now = set()
    try:
        for cat_id, prop_id, option_id, pages in PLAN:
            after = None
            flt = {
                "categoryId": cat_id, "regionId": BAKI, "isShop": None,
                "propertyOptions": {"boolean": [], "collection": [{"legacyId": prop_id, "value": option_id}],
                                    "range": [], "string": []},
            }
            for _ in range(pages):
                data = client.gql(LIST_QUERY, {"f": flt, "after": after})["adSearch"]["ads"]
                log(f"  tap.az siyahı: {len(data['nodes'])} elan")
                for node in data["nodes"]:
                    item_id = int(node["legacyResourceId"])
                    max_id = max(max_id, item_id)
                    sid = str(item_id)
                    if sid in seen_now or sid in known_ids:
                        continue
                    seen_now.add(sid)
                    if min_new_id is not None and item_id <= min_new_id:
                        continue
                    try:
                        d = client.gql(ITEM_QUERY, {"id": sid})["adDetails"]
                        if not d:
                            raise RuntimeError("elan tapılmadı")
                        results.append(_normalize(d))
                    except Bloklandi:
                        raise
                    except Exception as e:
                        errors.append(f"{sid}: {e}")
                if not data["pageInfo"]["hasNextPage"]:
                    break
                after = data["pageInfo"]["endCursor"]
    except Bloklandi as e:
        errors.append(f"BLOKLANMA ƏLAMƏTİ: {e}. Dayandım.")
    except requests.RequestException as e:
        errors.append(f"şəbəkə xətası: {e}")
    return results, errors, max_id
