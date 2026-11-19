"""yeniemlak.az toplayıcısı (Bakı, satış: mənzil + həyət evi/villa).

Sayt server HTML-dir. Elanda satıcı tipi yazılır ("Əmlak sahibi" / "Vasitəçi / Rieltor").

TELEFON: sayt nömrəni mətn kimi yox, şəkil kimi göstərir (`<img src="/tel-show/<nömrə>">`). Nömrə şəklin
ünvanında görünür, amma bu, saytın nömrəni skraperlərdən gizlətmək üçün qoyduğu qorumadır — onu oxumuruq.
Satıcını adı ilə tanıyırıq (`satıcı_açar`), telefon boş qalır.

Interfeys: SOURCE, fetch_latest(known_ids, min_new_id, reveal_phone, log) -> (elanlar, xetalar, max_id)
"""
import re
from datetime import date, datetime, timedelta

import requests
from bs4 import BeautifulSoup

from .common import TZ, Dayandi, Client, now_iso, split_location, to_float

SOURCE = "yeniemlak.az"
BASE = "https://yeniemlak.az"

# (emlak növü: 1 = bina evi/mənzil, 2 = həyət evi/villa; şəhər 7 = Bakı; səhifə sayı). elan_nov=1 satılır.
PLAN = [("1", "7", 1), ("2", "7", 1)]


def _text(el):
    return el.get_text(" ", strip=True) if el else None


def _list_cards(html):
    soup = BeautifulSoup(html, "lxml")
    cards, seen = [], set()
    for a in soup.select('a[href^="/elan/"]'):
        m = re.search(r"-(\d{4,})$", a["href"])
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        img = a.find("img")
        dm = re.search(r"get-img/(\d{2})(\d{2})(\d{4})W", (img.get("src") if img else "") or "")
        cards.append({"id": m.group(1), "href": a["href"],
                      "img_date": date(int(dm.group(3)), int(dm.group(2)), int(dm.group(1))) if dm else None})
    return cards


def _normalize(card, html):
    soup = BeautifulSoup(html, "lxml")
    full = soup.get_text(" ", strip=True)

    head = re.search(r"Satılır\s+([\d\s]+?)\s+Baxış sayı", full)
    price = to_float(head.group(1).replace(" ", "")) if head else None
    dm = re.search(r"Tarix:\s*(\d{2})\.(\d{2})\.(\d{4})", full)
    published = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}T00:00:00+04:00" if dm else None
    block = full[full.find("Elan:"):full.find("Ünvan")] if "Elan:" in full and "Ünvan" in full else full

    kind = None
    km = re.search(r"Elan:\s*\d+\s+(.+?)\s+\d", block)
    if km:
        kind = km.group(1).strip().lower()
    if kind and "yeni tikili" in kind:
        kind = "yeni tikili"
    elif kind and "köhnə tikili" in kind:
        kind = "köhnə tikili"
    rooms = re.search(r"(\d+)\s*otaq", block)
    area = re.search(r"([\d.]+)\s*m2", block)
    sot = re.search(r"([\d.]+)\s*sot", block)
    floor = floors = None
    fm = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})", block)
    if fm and int(fm.group(2)) >= int(fm.group(1)):
        floor, floors = int(fm.group(1)), int(fm.group(2))
    cixaris = True if "Kupça" in block else None
    checks = [(_text(c) or "").lower() for c in soup.select(".check")]
    temir = "var" if any("təmirli" in c for c in checks) else ("yoxdur" if any("təmirsiz" in c for c in checks) else None)
    ipoteka = True if any("ipoteka" in c for c in checks) or "ipoteka" in full.lower() else None

    params = [_text(p) for p in soup.select(".params")]
    city = next((p for p in params if p and p.startswith("Bakı")), None)
    rayon = qesebe = metro = None
    for p in params:
        if not p:
            continue
        if p.lower().startswith("metro."):
            metro = p.split(".", 1)[1].strip() + " m."
        elif "rayonu" in p.lower():
            rayon = re.sub(r"\s*rayonu$", " r.", p)
        elif "qəsəbə" in p.lower() or "qəs" in p.lower():
            qesebe = re.sub(r"\s*qəsəbəsi$", " q.", p)
    addr_text = None
    h = soup.find("h1", string=re.compile("Ünvan"))
    if h:
        t = h.find_next(class_="text")
        addr_text = _text(t)

    seller_name = _text(soup.select_one(".ad"))
    seller_type_raw = (_text(soup.select_one(".elvrn")) or "").lower()
    if "sahib" in seller_type_raw or "mülkiyyətçi" in seller_type_raw:
        tip = "mülkiyyətçi"
    elif "vasitəçi" in seller_type_raw or "rieltor" in seller_type_raw:
        tip = "vasitəçi"
    else:
        tip = seller_type_raw or None

    note = soup.find("h1", string=re.compile("Qeyd"))
    body = _text(note.find_next(class_="text")) if note else None

    photos = []
    for a in soup.select("a.fancybox-thumb"):
        u = a.get("href")
        if u and u not in photos:
            photos.append(u.replace("http://", "https://"))

    title = "Satılır " + (f"{rooms.group(1)} otaqlı " if rooms else "") + (kind or "əmlak")
    if area:
        title += f", {to_float(area.group(1)):g} m²"
    return {
        "mənbə": SOURCE,
        "elan_id": card["id"],
        "link": BASE + card["href"],
        "başlıq": title,
        "qiymət": price,
        "valyuta": "AZN",
        "kateqoriya": kind,
        "otaq_sayı": int(rooms.group(1)) if rooms else None,
        "sahə_m2": to_float(area.group(1)) if area else None,
        "torpaq_sahəsi_sot": to_float(sot.group(1)) if sot else None,
        "mərtəbə": floor,
        "ümumi_mərtəbə": floors,
        "rayon": rayon,
        "qəsəbə": qesebe,
        "metro": metro,
        "ünvan": ", ".join(x for x in [city, rayon, qesebe, addr_text] if x) or None,
        "təsvir": body,
        "şəkil_linkləri": photos,
        "çıxarış_var": cixaris,
        "təmir": temir,
        "ipoteka": ipoteka,
        "satıcı_tipi": tip,
        "satıcı_adı": seller_name,
        "telefon": None,
        "satıcı_açar": f"ye:{seller_name.strip().lower()}" if seller_name else None,
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
    oldest = datetime.now(TZ).date() - timedelta(days=1)
    try:
        for emlak, seher, pages in PLAN:
            for page in range(1, pages + 1):
                r = client.get(f"/elan/axtar?emlak={emlak}&elan_nov=1&seher%5B%5D={seher}&page={page}")
                cards = _list_cards(r.text)
                log(f"  yeniemlak.az siyahı: {len(cards)} elan")
                for card in cards:
                    iid = int(card["id"])
                    max_id = max(max_id, iid)
                    if card["id"] in seen_now or card["id"] in known_ids:
                        continue
                    seen_now.add(card["id"])
                    # ID-lər bu saytda yaranma sırasına tam uymur: ilk işləmədən sonra yalnız dünən/bu gün
                    # yüklənmiş şəkli olan (yəni təzə) elanlara baxırıq.
                    if min_new_id is not None and card["img_date"] and card["img_date"] < oldest:
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
