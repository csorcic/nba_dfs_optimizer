"""Small HTTP helper: one shared session, retries with backoff, polite pacing."""
from __future__ import annotations

import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "nba-dfs-optimizer (personal, non-commercial)"
TIMEOUT = 30

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        retry = Retry(total=4, backoff_factor=2, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET",), respect_retry_after_header=True)
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.headers["User-Agent"] = USER_AGENT
        _session = s
    return _session


def get(url: str, *, params=None, headers=None, pause: float = 0.0) -> requests.Response:
    """GET with retries. `pause` sleeps afterwards to stay polite to free APIs."""
    r = session().get(url, params=params, headers=headers, timeout=TIMEOUT)
    if pause:
        time.sleep(pause)
    return r
