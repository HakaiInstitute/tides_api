from functools import lru_cache

import requests
from ratelimit import limits, sleep_and_retry


class _CHSApi:
    def __init__(self):
        self.base_url = "https://api.iwls-sine.azure.cloud-nuage.dfo-mpo.gc.ca/api/v1"

    @staticmethod
    @sleep_and_retry
    @limits(calls=30, period=60)
    @limits(calls=3, period=1)
    def _rate_limit():
        """Check CHS rate limit."""
        return

    @lru_cache()
    def get(self, url):
        self._rate_limit()
        return requests.get(f"{self.base_url}{url}")


chs_api = _CHSApi()
