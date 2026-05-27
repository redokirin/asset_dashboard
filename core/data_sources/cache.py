# -*- coding: utf-8 -*-
import requests_cache


def install_requests_cache(cache_name="asset_tracking_cache", expire_after=600):
    """Install the shared requests cache used by market data fetchers."""
    requests_cache.install_cache(cache_name, expire_after=expire_after)
