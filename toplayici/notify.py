"""Telefona bildiriş (ntfy.sh): yeni EV SAHİBİ elanları gələndə.

ntfy.sh pulsuz push xidmətidir; telefonda "ntfy" tətbiqi qurulur və gizli bir "mövzuya" (topic) abunə olunur.
Mövzu adı NTFY_TOPIC mühit dəyişənindən (GitHub Secret) oxunur; yoxdursa heç nə göndərilmir.
Göndərilən məlumat yalnız ictimai elan məlumatıdır (qiymət, otaq, yer, link). Mövzu adı parol rolunu oynayır:
onu bilməyən abunə ola bilməz, ona görə gizli saxla və repoya yazma.
"""
import os
from datetime import datetime, timedelta, timezone

import requests

NTFY_URL = "https://ntfy.sh"
MAX_SEPARATE = 5      # bir işləmədə bundan çox ev sahibi elanı varsa, bir ümumi bildiriş göndərilir
MAX_AGE_HOURS = 24    # yerləşdirmə tarixi bundan köhnə olan elanlar haqqında bildiriş göndərilmir (ilk yığım axını)


def _fresh(item):
    iso = item.get("paylaşılma_tarixi")
    if not iso:
        return True
    try:
        return datetime.fromisoformat(iso) > datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    except ValueError:
        return True


def _title(it):
    parts = []
    if it.get("otaq_sayı"):
        parts.append(f"{it['otaq_sayı']} otaq")
    if it.get("sahə_m2"):
        parts.append(f"{it['sahə_m2']:g} m²")
    price = it.get("qiymət")
    head = " · ".join(parts) or (it.get("kateqoriya") or "Ev")
    if price:
        head += f" — {int(price):,} {it.get('valyuta') or 'AZN'}".replace(",", " ")
    return "Ev sahibi: " + head


def _post(payload):
    try:
        r = requests.post(NTFY_URL, json=payload, timeout=(10, 20))
        return r.ok
    except requests.RequestException as e:
        print(f"[bildiriş] göndərilmədi: {e}", flush=True)
        return False


def send_new_owner_ads(items, topic=None):
    """items: bu işləmədə tapılan YENİ elanlar. Yalnız 'ev sahibi' olanlar göndərilir. Göndərilən sayı qaytarır."""
    topic = topic or os.environ.get("NTFY_TOPIC")
    if not topic:
        return 0
    owners = [i for i in items if i.get("yeni") and i.get("makler_nəticə") == "ev sahibi" and _fresh(i)]
    if not owners:
        return 0
    if len(owners) > MAX_SEPARATE:
        ok = _post({"topic": topic, "title": f"{len(owners)} yeni ev sahibi elanı",
                    "message": "Tətbiqi açıb baxın.", "tags": ["house"], "priority": 3})
        return len(owners) if ok else 0
    sent = 0
    for it in owners:
        place = " · ".join(x for x in [it.get("rayon"), it.get("metro")] if x)
        msg = " | ".join(x for x in [place, it.get("mənbə")] if x)
        ok = _post({"topic": topic, "title": _title(it), "message": msg or (it.get("mənbə") or ""),
                    "click": it.get("link"), "tags": ["house"], "priority": 3})
        sent += 1 if ok else 0
    return sent
