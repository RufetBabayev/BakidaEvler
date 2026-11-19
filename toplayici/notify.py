"""Telefona bildiriş: yeni EV SAHİBİ elanı gələndə tətbiqi qurmuş bütün telefonlara (Expo Push + FCM).

Tətbiq girişdən sonra bildiriş icazəsi istəyir və Expo push tokenini Supabase-dəki `push_tokenlar`
cədvəlinə yazır. Toplayıcı bu tokenləri oxuyub https://exp.host/--/api/v2/push/send ünvanına göndərir.
Tokensiz (hələ heç kim qurmayıb) və ya Supabase rejimi olmadan heç nə göndərilmir.
"""
from datetime import datetime, timedelta, timezone

import requests

import db

EXPO_URL = "https://exp.host/--/api/v2/push/send"
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
    head = " · ".join(parts) or (it.get("kateqoriya") or "Ev")
    if it.get("qiymət"):
        head += f" — {int(it['qiymət']):,} {it.get('valyuta') or 'AZN'}".replace(",", " ")
    return "Ev sahibi: " + head


def _messages(owners):
    """Bildiriş mətnlərinin siyahısı (token əlavə olunmamış)."""
    if len(owners) > MAX_SEPARATE:
        return [{"title": f"{len(owners)} yeni ev sahibi elanı", "body": "Tətbiqi açıb baxın."}]
    out = []
    for it in owners:
        place = " · ".join(x for x in [it.get("rayon"), it.get("metro")] if x)
        out.append({"title": _title(it), "body": " | ".join(x for x in [place, it.get("mənbə")] if x) or "Yeni elan",
                    "data": {"url": it.get("link")}})
    return out


def _send(tokens, messages):
    """Hər mesajı hər tokenə göndərir (100-lük partiyalarla). Qeydiyyatsız tokenləri bazadan silir. Göndərilən sayı qaytarır."""
    batch, sent, dead = [], 0, set()
    for msg in messages:
        for t in tokens:
            batch.append({"to": t, "sound": "default", "channelId": "default", "priority": "high", **msg})
    for i in range(0, len(batch), 100):
        chunk = batch[i:i + 100]
        try:
            r = requests.post(EXPO_URL, json=chunk, timeout=(10, 30),
                              headers={"Accept": "application/json", "Content-Type": "application/json"})
            r.raise_for_status()
            for m, ticket in zip(chunk, r.json().get("data", [])):
                if ticket.get("status") == "ok":
                    sent += 1
                elif (ticket.get("details") or {}).get("error") == "DeviceNotRegistered":
                    dead.add(m["to"])
        except (requests.RequestException, ValueError) as e:
            print(f"[bildiriş] göndərilmədi: {e}", flush=True)
    for t in dead:
        try:
            db.delete_token(t)
        except Exception:
            pass
    return sent


def send_new_owner_ads(items):
    """items: bu işləmədə tapılan YENİ elanlar. Yalnız 'ev sahibi' olanlar göndərilir. Göndərilən sayı qaytarır."""
    if not db.enabled():
        return 0
    owners = [i for i in items if i.get("yeni") and i.get("makler_nəticə") == "ev sahibi" and _fresh(i)]
    if not owners:
        return 0
    tokens = db.fetch_tokens()
    if not tokens:
        return 0
    return _send(tokens, _messages(owners))
