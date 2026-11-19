"""BakıdaEvlər.az toplayıcısı.

İstifadə:
    python main.py              # ilk dəfə: siyahıdan başlayır; sonra: yalnız yeni elan ID-lərini yoxlayır
    python main.py --siyahi     # məcburi: siyahı rejimi (ilk quruluş kimi)
    python main.py --telefon    # YENİ elanlar üçün saytın "nömrəni göstər" sorğusunu da göndər
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import db
import makler
from scrapers import bina

SCRAPERS = [bina]

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SEEN_FILE = BASE_DIR / "seen.json"
TZ = timezone(timedelta(hours=4))
NAME = "BakıdaEvlər.az"


def load_seen():
    """seen.json: {"bina.az": {"son_max_id": N, "gozleyen": [ID...], "elanlar": {elan_id: {...}}}}"""
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("[xəbərdarlıq] seen.json oxunmadı, boş kimi qəbul edildi")
    return {}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=1), encoding="utf-8")


def run_source(scraper, state, args, now):
    """Bir saytı işlədir. Qaytarır: (elanlar, xetalar)."""
    seen = state["elanlar"]
    bootstrap = args.siyahi or state.get("son_max_id") is None

    if bootstrap:
        items, errors = scraper.fetch(set(seen), state.get("son_max_id"),
                                      reveal_phone=args.telefon, log=print)
        ids = [int(i["elan_id"]) for i in items]
        if ids and not errors:
            state["son_max_id"] = max(ids + ([state["son_max_id"]] if state.get("son_max_id") else []))
    else:
        items, errors, new_max, pending = scraper.fetch_incremental(
            state["son_max_id"], state.get("gozleyen", []), reveal_phone=args.telefon, log=print)
        items = [i for i in items if i["elan_id"] not in seen]
        state["son_max_id"], state["gozleyen"] = new_max, pending

    for it in items:
        if it["yeni"]:
            seen[it["elan_id"]] = {
                "ilk_görülmə": now.isoformat(timespec="seconds"),
                "satıcı_tipi": it.get("satıcı_tipi"),
                "satıcı_adı": it.get("satıcı_adı"),
                "telefon": it.get("telefon"),
            }
        else:  # siyahı rejimində əvvəl görülmüş elan: keşdən doldururuq
            cached = seen.get(it["elan_id"], {})
            it.update({"mənbə": scraper.SOURCE, "satıcı_tipi": cached.get("satıcı_tipi"),
                       "satıcı_adı": cached.get("satıcı_adı"), "telefon": cached.get("telefon"),
                       "toplanma_vaxtı": now.isoformat(timespec="seconds")})

    sayac = makler.say(seen)
    for it in items:
        makler.qiymetlendir(it, sayac)
    return items, errors


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--telefon", action="store_true", help="yeni elanlarda tam nömrəni də al")
    ap.add_argument("--siyahi", action="store_true", help="siyahı rejimini məcbur et")
    args = ap.parse_args()

    use_db = db.enabled()
    if use_db:
        print(f"[{NAME}] Supabase rejimi (vəziyyət bazada saxlanır)")
    else:
        DATA_DIR.mkdir(exist_ok=True)
    seen_all = {} if use_db else load_seen()
    now = datetime.now(TZ)
    all_items = []
    any_error = False

    for scraper in SCRAPERS:
        source = scraper.SOURCE
        if use_db:
            state = seen_all[source] = db.load_state(source)
        else:
            state = seen_all.setdefault(source, {"son_max_id": None, "gozleyen": [], "elanlar": {}})
        print(f"[{NAME}] {source}: toplanır...")
        items, errors = run_source(scraper, state, args, now)
        all_items.extend(items)
        if use_db:
            try:
                db.save(source, state, [i for i in items if i["yeni"]])
            except Exception as e:
                errors.append(f"bazaya yazma xətası: {e}")

        new = [i for i in items if i["yeni"]]
        owners = sum(1 for i in new if i.get("satıcı_tipi") == "mülkiyyətçi")
        agents = sum(1 for i in new if i.get("satıcı_tipi") == "vasitəçi")
        suspects = sum(1 for i in new if i.get("makler_nəticə") == "şübhəli makler")
        print(f"[{NAME}] {source}: {len(items)} elan toplandı | {len(new)} yeni | "
              f"{owners} mülkiyyətçi, {agents} vasitəçi | {suspects} şübhəli makler | {len(errors)} xəta")
        any_error = any_error or bool(errors)
        for e in errors:
            print("   xəta:", e)

    if use_db:
        print("Nəticə Supabase-ə yazıldı." if all_items else "Yeni elan yoxdur.")
        sys.exit(1 if any_error else 0)
    save_seen(seen_all)
    if all_items:
        out = DATA_DIR / f"bina_{now:%Y-%m-%d_%H%M}.json"
        out.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Fayl: {out.relative_to(BASE_DIR)}")
    else:
        print("Yeni elan yoxdur, fayl yazılmadı.")


if __name__ == "__main__":
    main()
