"""Makler aşkarlama: eyni telefonla çoxlu elan verən satıcı ev sahibi deyil.

Telefon maskalıdır (son 2 rəqəm gizli) — `--telefon` olmadan eyni açar 100 fərqli nömrəyə uyğun gələ bilər.
Elan sayı azdırsa təsadüfi üst-üstə düşmə mümkündür, ona görə hədd 3 elandır.
"""
from collections import Counter

HEDD = 3  # mülkiyyətçi kimi yazılıb, amma bu qədər və ya çox elanı var → şübhəli makler


def telefon_acari(telefon):
    return telefon.strip() if telefon else None


def say(seen_ads):
    """seen.json-dakı bütün elanlar üzrə telefon -> elan sayı."""
    return Counter(a for a in (telefon_acari(v.get("telefon")) for v in seen_ads.values()) if a)


def qiymetlendir(item, sayac):
    """Elana 'telefon_elan_sayı' və 'makler_nəticə' sahələrini əlavə edir."""
    key = telefon_acari(item.get("telefon"))
    n = sayac.get(key, 0) if key else 0
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
