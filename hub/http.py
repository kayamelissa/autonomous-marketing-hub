"""Shared HTTP session: timeouts, retries, honest User-Agent."""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "AutonomousMarketingHub/1.0 (+https://github.com/kayamelissa/autonomous-marketing-hub)"
)
DEFAULT_TIMEOUT = 30


def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset({"GET", "POST"}))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers["User-Agent"] = USER_AGENT
    return s


def get_json(url: str, *, params=None, headers=None, timeout: int = DEFAULT_TIMEOUT):
    r = session().get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.json()


def post_json(url: str, *, json=None, headers=None, params=None, timeout: int = 90):
    r = session().post(url, json=json, headers=headers, params=params, timeout=timeout)
    if r.status_code >= 400:
        raise requests.HTTPError(f"{r.status_code} from {url.split('?')[0]}: {r.text[:300]}", response=r)
    return r.json()
