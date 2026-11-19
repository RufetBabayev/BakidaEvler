"""Supabase ilə əlaqə (REST, yalnız `requests`).

Açarlar mühit dəyişənlərindən oxunur (kodda və ya gitdə saxlanmır):
    SUPABASE_URL           məs. https://abcd1234.supabase.co
    SUPABASE_SERVICE_KEY   service_role açarı (gizli!)
Bunlar yoxdursa toplayıcı köhnə qaydada yerli seen.json ilə işləyir.
"""
import os
from datetime import datetime, timezone

import requests

PAGE = 1000


def enabled():
    return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY"))


def _base():
    return os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1"


def _headers(extra=None):
    key = os.environ["SUPABASE_SERVICE_KEY"]
    h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    h.update(extra or {})
    return h


def _check(r):
    if not r.ok:
        raise RuntimeError(f"Supabase xətası {r.status_code}: {r.text[:300]}")
    return r


def load_state(source):
    """Əvvəlki işləmənin vəziyyəti: main.py-ın gözlədiyi quruluşda qaytarır."""
    state = {"son_max_id": None, "gozleyen": [], "elanlar": {}}
    r = _check(requests.get(f"{_base()}/toplayici_veziyyet", headers=_headers(),
                            params={"menba": f"eq.{source}", "select": "son_max_id,gozleyen"}, timeout=30))
    rows = r.json()
    if rows:
        state["son_max_id"] = rows[0]["son_max_id"]
        state["gozleyen"] = rows[0]["gozleyen"] or []

    offset = 0
    while True:
        r = _check(requests.get(
            f"{_base()}/elanlar", headers=_headers(),
            params={"menba": f"eq.{source}", "select": "elan_id,satici_tipi,satici_adi,telefon,ilk_gorulme",
                    "order": "elan_id", "limit": PAGE, "offset": offset}, timeout=60))
        rows = r.json()
        for x in rows:
            state["elanlar"][x["elan_id"]] = {
                "ilk_görülmə": x["ilk_gorulme"], "satıcı_tipi": x["satici_tipi"],
                "satıcı_adı": x["satici_adi"], "telefon": x["telefon"],
            }
        if len(rows) < PAGE:
            break
        offset += PAGE
    return state


def save(source, state, new_items):
    """Yeni elanları və vəziyyəti yazır (upsert)."""
    if new_items:
        rows = [{
            "menba": source,
            "elan_id": it["elan_id"],
            "link": it.get("link"),
            "qiymet": it.get("qiymət"),
            "valyuta": it.get("valyuta"),
            "kateqoriya": it.get("kateqoriya"),
            "otaq_sayi": it.get("otaq_sayı"),
            "sahe_m2": it.get("sahə_m2"),
            "rayon": it.get("rayon"),
            "metro": it.get("metro"),
            "satici_tipi": it.get("satıcı_tipi"),
            "satici_adi": it.get("satıcı_adı"),
            "telefon": it.get("telefon"),
            "telefon_elan_sayi": it.get("telefon_elan_sayı"),
            "makler_netice": it.get("makler_nəticə"),
            "yenilenme_tarixi": it.get("yenilənmə_tarixi"),
            "data": it,
        } for it in new_items]
        for i in range(0, len(rows), 200):
            _check(requests.post(f"{_base()}/elanlar", headers=_headers(
                {"Prefer": "resolution=merge-duplicates,return=minimal"}),
                params={"on_conflict": "menba,elan_id"}, json=rows[i:i + 200], timeout=60))

    _check(requests.post(f"{_base()}/toplayici_veziyyet", headers=_headers(
        {"Prefer": "resolution=merge-duplicates,return=minimal"}),
        params={"on_conflict": "menba"},
        json=[{"menba": source, "son_max_id": state.get("son_max_id"),
               "gozleyen": state.get("gozleyen", []), "yenilendi": datetime.now(timezone.utc).isoformat()}], timeout=30))
