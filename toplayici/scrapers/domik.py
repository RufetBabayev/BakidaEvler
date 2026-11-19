"""domik.az toplayıcısı (Bakı, satış: mənzil + həyət evi).

Sayt server HTML-dir. Elan ID-ləri yaranma sırası ilə artır. Elanda satıcı tipi ("Mülkiyyətçi" /
"Vasitəçi"), satıcı adı, yerləşdirmə/yenilənmə vaxtı və maskalı telefon (+994 51 318 ** **) var.

Interfeys: SOURCE, fetch_latest(known_ids, min_new_id, reveal_phone, log) -> (elanlar, xetalar, max_id)
"""
import re

import requests
from bs4 import BeautifulSoup

from .common import Dayandi, Client, now_iso, split_location, to_float

SOURCE = "domik.az"
BASE = "https://domik.az"

# (yol, səhifə sayı). Sıralama defolt "Yeni öncə".
PLAN = [("/elanlar/satis/menzil", 2), ("/elanlar/satis/heyet-evi", 1)]

# URL slug-ının rayon hissəsi (ASCII). Bakı rayonları; başqa şəhərləri atırıq.
BAKI_SLUG = ("xetai", "yasamal", "suraxani", "sabuncu", "abseron", "nesimi", "narimanov", "nerimanov", "nizami",
             "sebail", "xezer", "binaqadi", "bineqedi", "qaradag", "pirallahi")


def _list_cards(html):
    soup = BeautifulSoup(html, "lxml")
    cards, seen = [], set()
    for a in soup.select('a[href*="/elan/"]'):
        href = a["href"]
        m = re.search(r"/elan/(\d+)-([a-z0-9]+)", href)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        cards.append({"id": m.group(1), "href": href, "rayon_slug": m.group(2)})
    return cards


def _after(lines, label):
    for i, ln in enumerate(lines):
        if ln.strip().lower() == label.lower() and i + 1 < len(lines):
            return lines[i + 1].strip()
    return None


def _dt(text):
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})(?:\s+(\d{2}):(\d{2}))?", text or "")
    if not m:
        return None
    hh, mm = (m.group(4) or "00"), (m.group(5) or "00")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}T{hh}:{mm}:00+04:00"


def _yes(v):
    return (v or "").strip().lower() in ("var", "bəli", "beli")


def _normalize(card, html):
    soup = BeautifulSoup(html, "lxml")
    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).split("\n") if ln.strip()]
    full = "\n".join(lines)

    h1 = soup.select_one("h1")
    title = (h1.get_text(" ", strip=True) if h1 else None) or next((ln for ln in lines if ln.startswith("Satılır ")), "Satılır")
    kind = (_after(lines, "Kateqoriya") or "").lower() or None
    building = (_after(lines, "Tikili") or "").lower() or None
    kateqoriya = building if (kind == "mənzil" and building) else kind
    rooms = to_float(_after(lines, "Otaq sayı"))
    area = to_float(_after(lines, "Sahə, m²"))
    land = to_float(_after(lines, "Torpaq sahəsi, sot")) if _after(lines, "Torpaq sahəsi, sot") else None
    floor = floors = None
    fl = _after(lines, "Mərtəbə")
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", fl or "")
    if m:
        floor, floors = int(m.group(1)), int(m.group(2))
    repair = _after(lines, "Təmir")
    temir = ("var" if _yes(repair) else "yoxdur") if repair else None
    cixaris = _yes(_after(lines, "Çıxarış")) if _after(lines, "Çıxarış") else None
    ipoteka = _yes(_after(lines, "İpoteka")) if _after(lines, "İpoteka") else None

    # qiymət: "₼" sətrindən əvvəlki sətir
    price = None
    for i, ln in enumerate(lines):
        if ln == "₼" and i > 0:
            price = to_float(lines[i - 1].replace(" ", ""))
            break

    # yer: "Xətai · Həzi Aslanov · Məhəmməd Hadi küç. 78" və başlıqdakı "Xətai r." / "Həzi Aslanov q." / "... m."
    loc_line = next((ln for ln in lines if " · " in ln and not ln.startswith("m.")), None)
    rayon, qesebe, metro = split_location(*re.findall(r"[A-Za-zƏəİıÖöÜüŞşÇçĞğ0-9\- ]+? (?:r\.|q\.|m\.)", title))
    if not rayon and loc_line:
        first = loc_line.split(" · ")[0].strip()
        if first:
            rayon = first + " r."
    metro_val = _after(lines, "Metro")
    if metro_val and not metro:
        metro = metro_val + " m."
    address = loc_line

    # satıcı
    tip = None
    for ln in lines:
        low = ln.lower()
        if low == "mülkiyyətçi":
            tip = "mülkiyyətçi"
            break
        if low in ("vasitəçi", "agent", "agentlik"):
            tip = "vasitəçi"
            break
    seller_name = None
    phone = None
    for i, ln in enumerate(lines):
        if re.match(r"\+994[\d\s*]+", ln):
            phone = ln.replace("*", "●")
            if i >= 2:
                seller_name = lines[i - 2]  # ad, tip, telefon sırası
            break
    if seller_name and seller_name.lower() in ("ev sahibi", "mülkiyyətçi", "vasitəçi", "agent", "agentlik"):
        seller_name = None  # ad yazılmayıb, sayt ümumi "Ev sahibi" göstərir

    body = _after(lines, "Təsvir")
    photos = []
    for u in re.findall(r"https://domik\.az/uploads/listings/[A-Za-z0-9]+\.(?:jpg|jpeg|webp|png)", html):
        if u not in photos:
            photos.append(u)

    placed = re.search(r"Yerləşdirildi:\s*([\d.\s:]+)", full)
    updated = re.search(r"Yeniləndi:\s*([\d.\s:]+)", full)
    return {
        "mənbə": SOURCE,
        "elan_id": card["id"],
        "link": card["href"] if card["href"].startswith("http") else BASE + card["href"],
        "başlıq": "Satılır " + (f"{int(rooms)} otaqlı " if rooms else "") + (kateqoriya or "əmlak")
                  + (f", {area:g} m²" if area else ""),
        "qiymət": price,
        "valyuta": "AZN",
        "kateqoriya": kateqoriya,
        "otaq_sayı": int(rooms) if rooms else None,
        "sahə_m2": area,
        "torpaq_sahəsi_sot": land,
        "mərtəbə": floor,
        "ümumi_mərtəbə": floors,
        "rayon": rayon,
        "qəsəbə": qesebe,
        "metro": metro,
        "ünvan": ", ".join(x for x in ["Bakı", rayon, address] if x),
        "təsvir": body,
        "şəkil_linkləri": photos,
        "çıxarış_var": cixaris,
        "təmir": temir,
        "ipoteka": ipoteka,
        "satıcı_tipi": tip,
        "satıcı_adı": seller_name,
        "telefon": phone,
        "satıcı_açar": ("tel:" + phone) if phone else None,
        "paylaşılma_tarixi": _dt(placed.group(1) if placed else None),
        "yenilənmə_tarixi": _dt(updated.group(1) if updated else None),
        "toplanma_vaxtı": now_iso(),
        "yeni": True,
    }


def fetch_latest(known_ids, min_new_id=None, reveal_phone=False, log=print):
    """Siyahıdan ən yeni elanları götürür; yalnız YENİ və Bakıya aid olanların detalına girir."""
    client = Client(BASE)
    results, errors = [], []
    max_id = min_new_id or 0
    seen_now = set()
    try:
        for path, pages in PLAN:
            for page in range(1, pages + 1):
                r = client.get(f"{path}?page={page}")
                cards = _list_cards(r.text)
                log(f"  domik.az siyahı: {len(cards)} elan")
                for card in cards:
                    iid = int(card["id"])
                    max_id = max(max_id, iid)
                    if card["id"] in seen_now or card["id"] in known_ids:
                        continue
                    seen_now.add(card["id"])
                    if (min_new_id is not None and iid <= min_new_id) or card["rayon_slug"] not in BAKI_SLUG:
                        continue
                    try:
                        results.append(_normalize(card, client.get(card["href"]).text))
                    except Dayandi:
                        raise
                    except Exception as e:
                        errors.append(f"{card['id']}: {e}")
    except Dayandi as e:
        errors.append(str(e))
    except requests.RequestException as e:
        errors.append(f"şəbəkə xətası: {e}")
    return results, errors, max_id
