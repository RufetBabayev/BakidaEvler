"""BakıdaEvlər.az toplayıcısı.

İstifadə:
    python main.py                # bütün saytlardan yeni elanları topla
    python main.py --siyahi       # bina.az üçün siyahı rejimini məcbur et
    python main.py --telefon      # bina.az: YENİ elanlarda "nömrəni göstər" sorğusunu da göndər
    python main.py --sayt tap.az  # yalnız göstərilən sayt(lar)
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import db
import makler
import notify
from scrapers import bina, domik, rahatemlak, tap, vipemlak, yeniemlak

# Yeni sayt əlavə etmək: scrapers/<sayt>.py yaz və bura əlavə et.
SCRAPERS = [bina, tap, rahatemlak, vipemlak, yeniemlak, domik]

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SEEN_FILE = BASE_DIR / "seen.json"
TZ = timezone(timedelta(hours=4))
NAME = "BakıdaEvlər.az"


def load_seen():
    """seen.json: {sayt: {"son_max_id": N, "gozleyen": [ID...], "elanlar": {elan_id: {...}}}}"""
    if SEEN_FILE.exists():
        try:
            return json.loads(SEEN_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("[xəbərdarlıq] seen.json oxunmadı, boş kimi qəbul edildi")
    return {}


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=1), encoding="utf-8")


def run_source(scraper, state, args):
    """Bir saytı işlədir. Qaytarır: (elanlar, xetalar)."""
    seen = state["elanlar"]

    if hasattr(scraper, "fetch_latest"):  # siyahı əsaslı scraper
        items, errors, max_id = scraper.fetch_latest(
            set(seen), state.get("son_max_id"), reveal_phone=args.telefon, log=print)
        if not errors:
            state["son_max_id"] = max(max_id, state.get("son_max_id") or 0) or None
        return [i for i in items if i["elan_id"] not in seen], errors

    # bina.az: siyahıdan başla, sonra ID-ləri irəli skan et
    bootstrap = args.siyahi or state.get("son_max_id") is None
    if bootstrap:
        items, errors = scraper.fetch(set(seen), state.get("son_max_id"), reveal_phone=args.telefon, log=print)
        ids = [int(i["elan_id"]) for i in items]
        if ids and not errors:
            state["son_max_id"] = max(ids + ([state["son_max_id"]] if state.get("son_max_id") else []))
        # siyahı rejimində əvvəl görülmüş elanlar keşdən doldurulur və "yeni" sayılmır
        for it in items:
            if not it["yeni"]:
                c = seen.get(it["elan_id"], {})
                it.update({"mənbə": scraper.SOURCE, "satıcı_tipi": c.get("satıcı_tipi"),
                           "satıcı_adı": c.get("satıcı_adı"), "telefon": c.get("telefon"),
                           "satıcı_açar": c.get("satıcı_açar"),
                           "toplanma_vaxtı": datetime.now(TZ).isoformat(timespec="seconds")})
        return items, errors

    items, errors, new_max, pending = scraper.fetch_incremental(
        state["son_max_id"], state.get("gozleyen", []), reveal_phone=args.telefon, log=print)
    state["son_max_id"], state["gozleyen"] = new_max, pending
    return [i for i in items if i["elan_id"] not in seen], errors


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--telefon", action="store_true", help="bina.az: yeni elanlarda tam nömrəni də al")
    ap.add_argument("--siyahi", action="store_true", help="bina.az siyahı rejimini məcbur et")
    ap.add_argument("--sayt", action="append", help="yalnız bu sayt(lar), məs. --sayt tap.az")
    args = ap.parse_args()

    use_db = db.enabled()
    print(f"[{NAME}] {'Supabase rejimi (vəziyyət bazada)' if use_db else 'yerli rejim (seen.json)'}")
    if not use_db:
        DATA_DIR.mkdir(exist_ok=True)
    seen_all = {} if use_db else load_seen()
    now = datetime.now(TZ)

    scrapers = [s for s in SCRAPERS if not args.sayt or s.SOURCE in args.sayt]
    # 1) hər saytın vəziyyətini yüklə (makler sayı bütün saytlar üzrə hesablanır)
    for sc in SCRAPERS:
        if use_db:
            seen_all[sc.SOURCE] = db.load_state(sc.SOURCE)
        else:
            seen_all.setdefault(sc.SOURCE, {"son_max_id": None, "gozleyen": [], "elanlar": {}})
        seen_all[sc.SOURCE].setdefault("gozleyen", [])

    # 2) topla: saytlar PARALEL işləyir (hər saytın öz fasiləsi/Client-i var, eyni sayta eyni anda 1 sorğu)
    t_all = time.monotonic()
    results, times = {}, {}

    def work(sc):
        t0 = time.monotonic()
        print(f"[{NAME}] {sc.SOURCE}: başladı", flush=True)
        try:
            results[sc.SOURCE] = run_source(sc, seen_all[sc.SOURCE], args)
        except Exception as e:  # bir saytın xətası digərlərini dayandırmasın
            results[sc.SOURCE] = ([], [f"gözlənilməz xəta: {e}"])
        times[sc.SOURCE] = time.monotonic() - t0

    with ThreadPoolExecutor(max_workers=max(1, len(scrapers))) as pool:
        list(pool.map(work, scrapers))

    # 3) yeniləri keşə yaz, sonra makler qiymətləndirməsi (bütün saytlar üzrə)
    for sc in scrapers:
        items, _ = results[sc.SOURCE]
        seen = seen_all[sc.SOURCE]["elanlar"]
        for it in items:
            if it["yeni"]:
                seen[it["elan_id"]] = {
                    "ilk_görülmə": now.isoformat(timespec="seconds"),
                    "satıcı_tipi": it.get("satıcı_tipi"), "satıcı_adı": it.get("satıcı_adı"),
                    "telefon": it.get("telefon"), "satıcı_açar": it.get("satıcı_açar"),
                }
    sayac = makler.say(seen_all)

    all_items, any_error, notify_items = [], False, []
    ok_sites, total_new = 0, 0
    for sc in scrapers:
        items, errors = results[sc.SOURCE]
        for it in items:
            makler.qiymetlendir(it, sayac)
        new = [i for i in items if i["yeni"]]
        if use_db:
            try:
                db.save(sc.SOURCE, seen_all[sc.SOURCE], new)
            except Exception as e:
                errors.append(f"bazaya yazma xətası: {e}")
        owners = sum(1 for i in new if i.get("satıcı_tipi") == "mülkiyyətçi")
        agents = sum(1 for i in new if i.get("satıcı_tipi") == "vasitəçi")
        suspects = sum(1 for i in new if i.get("makler_nəticə") == "şübhəli makler")
        sec = times.get(sc.SOURCE, 0)
        blocked = next((e for e in errors if e.startswith("BLOKLANDI")), None)
        timeout = next((e for e in errors if e.startswith("VAXT BİTDİ")), None)
        if blocked:
            print(f"[{NAME}] {sc.SOURCE:<14}→ {blocked} | {len(new)} yeni (bloklanmadan əvvəl) | {sec:.0f} s", flush=True)
        else:
            extra = f" | {timeout}" if timeout else ""
            print(f"[{NAME}] {sc.SOURCE:<14}→ {len(items)} elan | {len(new)} yeni | "
                  f"{owners} mülkiyyətçi, {agents} vasitəçi, {suspects} şübhəli | {len(errors) - (1 if timeout else 0)} xəta"
                  f"{extra} | {sec:.0f} s", flush=True)
        for e in errors:
            if not e.startswith(("BLOKLANDI", "VAXT BİTDİ")):
                print("   xəta:", e, flush=True)
        if not blocked and not [e for e in errors if not e.startswith("VAXT BİTDİ")]:
            ok_sites += 1
        any_error = any_error or bool([e for e in errors if not e.startswith(("BLOKLANDI", "VAXT BİTDİ"))])
        total_new += len(new)
        all_items.extend(items)
        if not any(e.startswith("bazaya yazma xətası") for e in errors):
            notify_items.extend(new)  # yalnız bazaya yazılanlar haqqında bildiriş

    total = time.monotonic() - t_all
    try:
        sent = notify.send_new_owner_ads(notify_items)
        if sent:
            print(f"[{NAME}] bildiriş: {sent} ev sahibi elanı göndərildi", flush=True)
    except Exception as e:  # bildiriş xətası toplamağı pozmasın
        print(f"[bildiriş] xəta: {e}", flush=True)
    print(f"[{NAME}] CƏMİ: {ok_sites}/{len(scrapers)} sayt uğurlu | {total_new} yeni elan | "
          f"{int(total // 60)} dəq {int(total % 60)} s", flush=True)

    if use_db:
        print("Nəticə Supabase-ə yazıldı." if all_items else "Yeni elan yoxdur.")
        sys.exit(1 if any_error else 0)
    save_seen(seen_all)
    if all_items:
        out = DATA_DIR / f"elanlar_{now:%Y-%m-%d_%H%M}.json"
        out.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Fayl: {out.relative_to(BASE_DIR)}")
    else:
        print("Yeni elan yoxdur, fayl yazılmadı.")


if __name__ == "__main__":
    main()
