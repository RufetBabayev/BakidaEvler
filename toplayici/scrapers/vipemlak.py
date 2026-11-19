"""vipemlak.az toplayıcısı (Bakı, satış: yeni tikili, köhnə tikili, həyət evi/villa).

Sayt köhnə tipli server HTML-dir. Elan ID-ləri yaranma sırası ilə artır. Satıcı tipi ("mülkiyyətçi" /
"vasitəçi") elanda yazılmır; satıcı hesabının ID-si (/user/NNN) var, ona görə satıcını hesab ID-si ilə
tanıyırıq (`satıcı_açar`) və tipi eyni satıcının elan sayına görə makler.py təxmin edir.
Telefon maskalıdır: 0555599XXX.

Interfeys: SOURCE, fetch_latest(known_ids, min_new_id, reveal_phone, log) -> (elanlar, xetalar, max_id)
"""
import re

import requests
from bs4 import BeautifulSoup

from .common import Dayandi, Client, now_iso, split_location, to_float

SOURCE = "vipemlak.az"
BASE = "https://vipemlak.az"

# (kateqoriya yolu, səhifə sayı)
PLAN = [("/yeni-tikili", 2), ("/kohne-tikili", 1), ("/heyet-evi-villa", 1)]

BAKI_RAYONLARI = ("binəqədi", "xətai", "nəsimi", "nərimanov", "nizami", "səbail", "suraxanı", "sabunçu",
                  "xəzər", "yasamal", "qaradağ", "pirallahı", "abşeron")


def _text(el):
    return el.get_text(" ", strip=True) if el else None


def _is_baku(title):
    t = (title or "").lower()
    return any(t.startswith(r) for r in BAKI_RAYONLARI)


def _list_cards(html):
    soup = BeautifulSoup(html, "lxml")
    cards = []
    for c in soup.select("div.pranto"):
        a = c.select_one("a[href$='.html']")
        if not a:
            continue
        m = re.search(r"-(\d+)\.html$", a["href"])
        if not m:
            continue
        cards.append({"id": m.group(1), "href": a["href"], "title": a.get("title") or _text(c.select_one("h3"))})
    return cards


def _value_after(lines, label):
    for i, ln in enumerate(lines):
        if ln.strip().lower() == label.lower() and i + 1 < len(lines):
            return lines[i + 1].strip()
    return None


def _normalize(card, html):
    soup = BeautifulSoup(html, "lxml")
    lines = [ln.strip() for ln in soup.get_text("\n", strip=True).split("\n") if ln.strip()]
    h1 = _text(soup.select_one("h1")) or card["title"] or ""

    kind = (_value_after(lines, "Əmlakın növü") or "").lower() or None
    rooms = to_float(_value_after(lines, "Otaq sayı"))
    area = to_float(_value_after(lines, "Sahə"))
    price_text = _value_after(lines, "Qiymət")
    price = to_float((price_text or "").replace(" ", ""))
    cur = "AZN" if price_text and "azn" in price_text.lower() else None

    addr = soup.find("b", string=re.compile(r"Ünvan:"))
    addr_box = addr.find_parent() if addr else None
    parts = [(x.next_sibling.strip() if isinstance(x.next_sibling, str) else "")
             for x in (addr_box.select(".sep") if addr_box else [])]
    parts = [p for p in parts if p]
    city = parts[0] if parts else None
    rayon, qesebe, metro = split_location(*[
        re.sub(r"\s*rayonu$", " r.", re.sub(r"\s*qəsəbəsi$", " q.", re.sub(r"\s*metrosu$", " m.", p))) for p in parts])
    street = None
    if addr_box:
        tail = [s.strip() for s in addr_box.find_all(string=True, recursive=False) if s.strip() and s.strip() not in ("•",)]
        street = tail[-1] if tail else None
        if street in parts:
            street = None

    body_box = soup.find("strong", string=re.compile("Ümumi məlumat"))
    body = None
    if body_box:
        body = body_box.find_parent().get_text(" ", strip=True).replace("Ümumi məlumat", "", 1).strip() or None

    floor = floors = None
    m = re.search(r"\b(\d{1,2})\s*/\s*(\d{1,2})\b", body or "")
    if m and int(m.group(2)) >= int(m.group(1)):
        floor, floors = int(m.group(1)), int(m.group(2))

    low = (body or "").lower()
    cixaris = True if re.search(r"kup[çc]a|[çc][ıi]xar[ıi]ş", low) else None
    ipoteka = True if "ipoteka" in low else None
    temir = "var" if re.search(r"təmirli|temirli|əla təmir|yeni təmir", low) else (
        "yoxdur" if re.search(r"təmirsiz|temirsiz", low) else None)

    seller_a = soup.select_one("a[href^='/user/']")
    seller_name = _text(seller_a.select_one(".infusrlogin")) if seller_a else None
    seller_id = re.search(r"/user/(\d+)", seller_a["href"]).group(1) if seller_a else None
    tel = soup.select_one("#telshow")
    phone = None
    if tel:
        raw = tel.get_text("", strip=True).replace("nömrəni göstər", "").strip()
        if raw:
            phone = raw.replace("X", "●").replace("x", "●")

    date_el = soup.find(string=re.compile(r"Tarix:\s*\d"))
    published = None
    if date_el:
        dm = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", date_el)
        if dm:
            published = f"{dm.group(3)}-{dm.group(2)}-{dm.group(1)}T00:00:00+04:00"

    photos = []
    for u in re.findall(r"/uploads/news/vipemlak_[A-Za-z0-9]+\.jpe?g", html):
        full = BASE + u
        if full not in photos:
            photos.append(full)

    if "yeni tikili" in (kind or ""):
        kind = "yeni tikili"
    title = f"Satılır {int(rooms)} otaqlı {kind}" if rooms and kind else "Satılır " + (kind or "əmlak")
    if area:
        title += f", {area:g} m²"
    return {
        "mənbə": SOURCE,
        "elan_id": card["id"],
        "link": BASE + card["href"],
        "başlıq": title,
        "qiymət": price,
        "valyuta": cur,
        "kateqoriya": kind,
        "otaq_sayı": int(rooms) if rooms else None,
        "sahə_m2": area,
        "torpaq_sahəsi_sot": None,
        "mərtəbə": floor,
        "ümumi_mərtəbə": floors,
        "rayon": rayon,
        "qəsəbə": qesebe,
        "metro": metro,
        "ünvan": ", ".join(x for x in [city, rayon, qesebe, street] if x) or h1,
        "təsvir": body,
        "şəkil_linkləri": photos,
        "çıxarış_var": cixaris,
        "təmir": temir,
        "ipoteka": ipoteka,
        "satıcı_tipi": None,  # saytda yazılmır
        "satıcı_adı": seller_name,
        "telefon": phone,
        "satıcı_açar": f"vip:{seller_id}" if seller_id else None,
        "paylaşılma_tarixi": published,
        "yenilənmə_tarixi": None,
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
                r = client.get(path + (f"/?start={page}" if page > 1 else ""))
                cards = _list_cards(r.text)
                log(f"  vipemlak.az siyahı: {len(cards)} elan")
                for card in cards:
                    iid = int(card["id"])
                    max_id = max(max_id, iid)
                    if card["id"] in seen_now or card["id"] in known_ids:
                        continue
                    seen_now.add(card["id"])
                    if (min_new_id is not None and iid <= min_new_id) or not _is_baku(card["title"]):
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
