"""rahatemlak.az toplayıcısı (Bakı, satış: mənzil + həyət/bağ evi).

Sayt server tərəfindən HTML verir (BeautifulSoup). Elan ID-ləri yaranma sırası ilə artır və
elanda "Əlavə olunub" (paylaşılma vaxtı) və satıcı tipi ("Mülkiyyətçi" / "Vasitəçi (agent)") yazılır.
Telefon maskalıdır: (051) 744-XX-XX.

Interfeys: SOURCE, fetch_latest(known_ids, min_new_id, reveal_phone, log) -> (elanlar, xetalar, max_id)
"""
import re

import requests
from bs4 import BeautifulSoup

from .common import Dayandi, Client, now_iso, parse_az_date, split_location, to_float

SOURCE = "rahatemlak.az"
BASE = "https://rahatemlak.az"

# (property_type, səhifə sayı): 8 = Mənzillər (yeni+köhnə tikili), 3 = Həyət/Bağ evi. ad_type=1 satış, city=6 Bakı.
PLAN = [("8", 2), ("3", 1)]


def _text(el):
    return el.get_text(" ", strip=True) if el else None


def _list_cards(html):
    soup = BeautifulSoup(html, "lxml")
    cards = []
    for a in soup.select('a[href*="/elan/"]'):
        m = re.search(r"/elan/(\d+)", a["href"])
        if not m or not a.select_one(".property-card-footer"):
            continue
        cards.append({
            "id": m.group(1),
            "price": _text(a.select_one(".amount")),
            "spans": [_text(s) for s in a.select(".property-card-middle li span")],
            "name": _text(a.select_one(".property-card-footer .name")),
            "location": _text(a.select_one(".location")),
            "date": _text(a.select_one(".date")),
            "features": [f.get("data-info") or "" for f in a.select(".property-card-features span[data-info]")],
        })
    return cards


def _parse_price(text):
    if not text:
        return None, None
    num = re.sub(r"[^\d.]", "", text.replace(",", ""))
    cur = "AZN" if "AZN" in text else ("USD" if ("USD" in text or "$" in text) else None)
    return (float(num) if num else None), cur


def _yes(value):
    v = (value or "").lower()
    return ("var" in v) and ("yox" not in v)


def _normalize(card, detail_html):
    soup = BeautifulSoup(detail_html, "lxml")
    ov = {}
    for box in soup.select(".overview-box"):
        t = _text(box.select_one(".overview-box-content-title"))
        if t:
            ov[t.strip().lower().replace("̇", "")] = _text(box.select_one(".overview-box-content-text"))
    loc = {}
    for box in soup.select(".location-box"):
        t = _text(box.select_one(".location-box-title"))
        if t:
            loc[t.strip().rstrip(":").lower()] = _text(box.select_one(".location-box-text"))

    seller = _text(soup.select_one(".author-content-type")) or ""
    seller_name = _text(soup.select_one(".author-content-name"))
    phone = None
    block = soup.select_one(".card-author")
    block = block.find_parent(class_="sidebar-card") if block else None
    found = re.search(r"\(\d{3}\)\s*\d{3}-[\dXx-]+", block.get_text(" ", strip=True)) if block else None
    if found:
        phone = found.group(0).replace("X", "●").replace("x", "●")

    added = None
    marker = soup.find(string=re.compile("Əlavə olunub"))
    if marker:
        added = _text(marker.find_parent().find_next_sibling())
    published = parse_az_date(added or card["date"])

    photos = []
    for img in soup.select("img[data-stat='product-gallery-item']"):
        u = img.get("data-src") or img.get("src")
        if u and u.startswith("http") and u not in photos:
            photos.append(u)

    price, cur = _parse_price(card["price"])
    kind = (ov.get("əmlak növü") or "").lower() or None
    rooms = area = floor = floors = None
    for s in card["spans"]:
        if not s:
            continue
        m = re.match(r"(\d+)\s*otaq", s)
        if m:
            rooms = int(m.group(1))
        elif "m²" in s:
            area = to_float(s)
        else:
            m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", s)
            if m:
                floor, floors = int(m.group(1)), int(m.group(2))
    land = None
    for k, v in ov.items():
        if "torpaq" in k and "sahə" in k:
            land = to_float(v)
    rayon, qesebe, metro = split_location(card["location"])
    if not rayon and loc.get("rayon"):
        rayon = loc["rayon"] + " r."
    cixaris = ipoteka = temir = None
    for k, v in ov.items():
        if "çıxarış" in k:
            cixaris = _yes(v)
        elif "ipoteka" in k:
            ipoteka = _yes(v)
        elif "təmir" in k:
            temir = "yoxdur" if "yox" in (v or "").lower() or "təmirsiz" in (v or "").lower() else "var"

    feats = " ".join(card.get("features") or []).lower().replace("̇", "")
    if ipoteka is None and "ipoteka" in feats:
        ipoteka = True
    if cixaris is None and "çıxarış" in feats:
        cixaris = True
    if temir is None and "təmir" in feats:
        temir = "yoxdur" if "təmirsiz" in feats else "var"

    low = seller.lower()
    if "vasitəçi" in low or "agent" in low:
        tip = "vasitəçi"
    elif "mülkiyyətçi" in low or "sahib" in low:
        tip = "mülkiyyətçi"
    else:
        tip = seller or None

    title = card["name"] or "Satılır"
    return {
        "mənbə": SOURCE,
        "elan_id": card["id"],
        "link": f"{BASE}/elan/{card['id']}",
        "başlıq": "Satılır " + title.lower() + (f", {area:g} m²" if area else ""),
        "qiymət": price,
        "valyuta": cur,
        "kateqoriya": kind,
        "otaq_sayı": rooms,
        "sahə_m2": area,
        "torpaq_sahəsi_sot": land,
        "mərtəbə": floor,
        "ümumi_mərtəbə": floors,
        "rayon": rayon,
        "qəsəbə": qesebe,
        "metro": metro,
        "ünvan": ", ".join(x for x in ["Bakı", rayon or card["location"], loc.get("ünvan")] if x),
        "təsvir": _text(soup.select_one(".text-box")),
        "şəkil_linkləri": photos,
        "çıxarış_var": cixaris,
        "təmir": temir,
        "ipoteka": ipoteka,
        "satıcı_tipi": tip,
        "satıcı_adı": seller_name,
        "telefon": phone,
        "satıcı_açar": ("tel:" + phone) if phone else None,
        "paylaşılma_tarixi": published,
        "yenilənmə_tarixi": None,
        "toplanma_vaxtı": now_iso(),
        "yeni": True,
    }


def fetch_latest(known_ids, min_new_id=None, reveal_phone=False, log=print):
    """Siyahıdan ən yeni elanları götürür; yalnız YENİ olanların (əvvəl görülməyib və ID > əvvəlki max) detalına girir."""
    client = Client(BASE)
    results, errors = [], []
    max_id = min_new_id or 0
    seen_now = set()
    try:
        for ptype, pages in PLAN:
            for page in range(1, pages + 1):
                r = client.get(f"/search-property?ad_type=1&city=6&property_type={ptype}&page={page}")
                cards = _list_cards(r.text)
                log(f"  rahatemlak.az siyahı: {len(cards)} elan")
                for card in cards:
                    iid = int(card["id"])
                    max_id = max(max_id, iid)
                    if card["id"] in seen_now or card["id"] in known_ids:
                        continue
                    seen_now.add(card["id"])
                    if min_new_id is not None and iid <= min_new_id:
                        continue
                    try:
                        results.append(_normalize(card, client.get(f"/elan/{card['id']}").text))
                    except Dayandi:
                        raise
                    except Exception as e:
                        errors.append(f"{card['id']}: {e}")
    except Dayandi as e:
        errors.append(str(e))
    except requests.RequestException as e:
        errors.append(f"şəbəkə xətası: {e}")
    return results, errors, max_id
