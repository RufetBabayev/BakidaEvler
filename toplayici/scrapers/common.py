"""Bütün scraper-lər üçün ümumi köməkçilər: nəzakətli HTTP, vaxt, mətn təmizləmə."""
import os
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
DELAY = (2.0, 4.0)          # eyni sayta sorğular arası təsadüfi fasilə (saniyə); 2 san-dən az OLMAZ
TIMEOUT = (10, 20)          # (connect, read) saniyə
RETRIES = 2                 # şəbəkə xətasında maksimum təkrar
SITE_TIME_LIMIT = int(os.environ.get("SITE_TIME_LIMIT", "180"))  # hər sayta maksimum vaxt (saniyə)
BLOCK_STATUSES = (403, 429, 503)
BLOCK_MARKERS = ("captcha", "cf-chl", "just a moment", "attention required", "cloudflare ray id")


class Dayandi(Exception):
    """Saytı dayandırırıq (bloklanma və ya vaxt limiti); topladığımız saxlanılır, digər saytlar davam edir."""


class Bloklandi(Dayandi):
    """Sayt sorğunu rədd etdi (403/429/503/Cloudflare/captcha). Keçmirik, yalnız bildiririk."""


class VaxtBitdi(Dayandi):
    """Saytın vaxt limiti bitdi."""


def now_iso():
    return datetime.now(TZ).isoformat(timespec="seconds")


class Client:
    """requests.Session + 2-4 san fasilə + timeout/retry + bloklanma aşkarı + vaxt limiti.

    Hər sayt öz Client-ini yaradır, yəni eyni sayta eyni anda yalnız 1 sorğu gedir.
    """

    def __init__(self, base, headers=None, time_limit=None):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "az,en;q=0.8"})
        if headers:
            self.s.headers.update(headers)
        self._first = True
        self.requests_made = 0
        self.last_status = None
        self.deadline = time.monotonic() + (time_limit if time_limit is not None else SITE_TIME_LIMIT)
        self.limit = time_limit if time_limit is not None else SITE_TIME_LIMIT

    def _wait(self):
        if time.monotonic() >= self.deadline:
            raise VaxtBitdi(f"VAXT BİTDİ ({self.limit} san)")
        if not self._first:
            time.sleep(random.uniform(*DELAY))
        self._first = False

    def _send(self, method, url, **kw):
        last = None
        for attempt in range(RETRIES + 1):
            if time.monotonic() >= self.deadline:
                raise VaxtBitdi(f"VAXT BİTDİ ({self.limit} san)")
            try:
                r = self.s.request(method, url, timeout=TIMEOUT, **kw)
                break
            except (requests.ConnectionError, requests.Timeout) as e:
                last = e
                if attempt < RETRIES:
                    time.sleep(2 * (attempt + 1))
        else:
            raise last
        self.requests_made += 1
        self.last_status = r.status_code
        low = r.text[:3000].lower()
        if r.status_code in BLOCK_STATUSES or any(m in low for m in BLOCK_MARKERS):
            raise Bloklandi(f"BLOKLANDI: status {r.status_code}")
        r.raise_for_status()
        return r

    def get(self, path_or_url, **kw):
        self._wait()
        url = path_or_url if path_or_url.startswith("http") else self.base + path_or_url
        return self._send("GET", url, **kw)

    def gql(self, query, variables, path="/graphql"):
        self._wait()
        r = self._send("POST", self.base + path, json={"query": query, "variables": variables})
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


_AY = {"yanvar": 1, "fevral": 2, "mart": 3, "aprel": 4, "may": 5, "iyun": 6, "iyul": 7,
       "avqust": 8, "sentyabr": 9, "oktyabr": 10, "noyabr": 11, "dekabr": 12}


_HEFTE = [("bazar ertəsi", 0), ("çərşənbə axşamı", 1), ("çərşənbə", 2), ("cümə axşamı", 3),
          ("cümə", 4), ("şənbə", 5), ("bazar", 6)]


def parse_az_date(text, now=None):
    """'Bu gün, 14:48' / 'Dünən, 16:15' / '10 Noyabr, 18:19' / '10 Noyabr 2025' -> ISO (+04:00). Tanınmazsa None."""
    if not text:
        return None
    now = now or datetime.now(TZ)
    t = text.strip().lower()
    hm = re.search(r"(\d{1,2}):(\d{2})", t)
    hour, minute = (int(hm.group(1)), int(hm.group(2))) if hm else (0, 0)
    day = None
    if "bu gün" in t or "bugün" in t:
        day = now.date()
    elif "dünən" in t:
        day = (now - timedelta(days=1)).date()
    elif any(t.startswith(name) for name, _ in _HEFTE):
        wd = next(i for name, i in _HEFTE if t.startswith(name))
        back = (now.weekday() - wd) % 7 or 7
        day = (now - timedelta(days=back)).date()
    else:
        m = re.search(r"(\d{1,2})\s+([a-zəıöüşçğ]+)(?:\s+(\d{4}))?", t)
        if m and m.group(2) in _AY:
            year = int(m.group(3)) if m.group(3) else now.year
            try:
                day = datetime(year, _AY[m.group(2)], int(m.group(1))).date()
                if not m.group(3) and day > now.date():
                    day = day.replace(year=year - 1)
            except ValueError:
                day = None
    if day is None:
        return None
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ).isoformat(timespec="seconds")
