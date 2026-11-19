"""Bütün scraper-lər üçün ümumi köməkçilər: nəzakətli HTTP, vaxt, mətn təmizləmə."""
import random
import re
import time
from datetime import datetime, timedelta, timezone

import requests

TZ = timezone(timedelta(hours=4))  # Bakı vaxtı
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
DELAY = (2.0, 4.0)  # sorğular arası təsadüfi fasilə (saniyə)


class Bloklandi(Exception):
    """Sayt sorğunu rədd etdi (403/429/captcha). Davam etmirik, keçmirik."""


def now_iso():
    return datetime.now(TZ).isoformat(timespec="seconds")


class Client:
    """requests.Session + hər sorğudan əvvəl 2-4 san gözləmə + bloklanma aşkarı."""

    def __init__(self, base, headers=None):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "az,en;q=0.8"})
        if headers:
            self.s.headers.update(headers)
        self._first = True

    def _wait(self):
        if not self._first:
            time.sleep(random.uniform(*DELAY))
        self._first = False

    def _check(self, r):
        if r.status_code in (403, 429) or "captcha" in r.text[:3000].lower():
            raise Bloklandi(f"HTTP {r.status_code}: sayt sorğunu qəbul etmədi")
        r.raise_for_status()
        return r

    def get(self, path_or_url, **kw):
        self._wait()
        url = path_or_url if path_or_url.startswith("http") else self.base + path_or_url
        return self._check(self.s.get(url, timeout=30, **kw))

    def gql(self, query, variables, path="/graphql"):
        self._wait()
        r = self._check(self.s.post(self.base + path, json={"query": query, "variables": variables}, timeout=30))
        data = r.json()
        if data.get("errors") and not data.get("data"):
            raise RuntimeError(data["errors"][0].get("message", "GraphQL xətası"))
        return data["data"]


def to_float(text):
    """'111', '111,5', '2 800 m²' -> float; tapılmazsa None."""
    if text is None:
        return None
    m = re.search(r"\d[\d\s.,]*", str(text))
    if not m:
        return None
    s = m.group(0).strip().replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def split_location(*names):
    """Yer adlarını sonluğuna görə rayon / qəsəbə / metro-ya ayırır."""
    rayon = qesebe = metro = None
    for n in names:
        if not n:
            continue
        low = n.lower().strip()
        if low.endswith(" m.") or low.endswith(" metrosu"):
            metro = metro or n.strip()
        elif low.endswith(" r.") or low.endswith(" rayonu"):
            rayon = rayon or n.strip()
        elif low.endswith(" q.") or low.endswith(" qəs.") or low.endswith(" qəsəbəsi") or low.endswith(" mtk"):
            qesebe = qesebe or n.strip()
    return rayon, qesebe, metro


def text_flags(body):
    """Təsvir mətnindən çıxarış / ipoteka / təmir işarələri. Mətndə yoxdursa None (naməlum)."""
    low = (body or "").lower()
    cixaris = True if re.search(r"kup[çc]a|[çc][ıi]xar[ıi]ş|[çc]ixaris|kupcali", low) else None
    ipoteka = True if "ipoteka" in low else None
    temir = "var" if re.search(r"təmirli|temirli|evro\s?təmir|əla təmir|yeni təmir", low) else (
        "yoxdur" if re.search(r"təmirsiz|temirsiz", low) else None)
    return cixaris, ipoteka, temir
