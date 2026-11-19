"""Makler aşkarlama: eyni satıcı (telefon və ya sayt hesabı) çoxlu elan verirsə, o ev sahibi deyil.

Satıcı açarı (`satıcı_açar`): bina.az üçün "tel:<maskalı telefon>", tap.az üçün "tap:<istifadəçi ID>".
Bina.az telefonu maskalıdır (son 2 rəqəm gizli), ona görə təsadüfi üst-üstə düşmə mümkündür; hədd 3 elandır.
Sayt özü satıcının ümumi elan sayını verirsə (`satıcının_elan_sayı`) və o 5 və çoxdursa, onu da nəzərə alırıq.
"""
from collections import Counter

HEDD = 3          # mülkiyyətçi kimi yazılıb, amma bu qədər və ya çox elanı var → şübhəli makler
SAYT_HEDD = 5     # saytın bildirdiyi ümumi elan sayı bu həddi keçirsə nəzərə alınır


def acar(item_or_cache):
    """Elanın/keş qeydinin satıcı açarı."""
    a = item_or_cache.get("satıcı_açar")
    if a:
        return a
    tel = (item_or_cache.get("telefon") or "").strip()
    return "tel:" + tel if tel else None


def say(seen_all):
    """Bütün saytların seen vəziyyəti üzrə satıcı açarı -> elan sayı."""
    c = Counter()
    for state in seen_all.values():
        for v in state.get("elanlar", {}).values():
            a = acar(v)
            if a:
                c[a] += 1
    return c


def qiymetlendir(item, sayac):
    """Elana 'telefon_elan_sayı' (satıcının elan sayı) və 'makler_nəticə' sahələrini əlavə edir."""
    a = acar(item)
    n = sayac.get(a, 0) if a else 0
    site_n = item.get("satıcının_elan_sayı") or 0
    if site_n >= SAYT_HEDD:
        n = max(n, site_n)
    tip = item.get("satıcı_tipi")
    if tip == "vasitəçi":
        netice = "makler"
    elif tip == "mülkiyyətçi" and n >= HEDD:
        netice = "şübhəli makler"
    elif tip == "mülkiyyətçi":
        netice = "ev sahibi"
    else:
        netice = None
    item["telefon_elan_sayı"] = n or None
    item["makler_nəticə"] = netice
    return item
