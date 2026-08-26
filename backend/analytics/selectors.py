from django.core.cache import cache

CACHE_VERSION_KEYS = {
    "web": "analytics:web:version",
    "commercial": "analytics:commercial:version",
}


def analytics_cache_version(namespace):
    key = CACHE_VERSION_KEYS[namespace]
    cache.add(key, 1, timeout=None)
    return int(cache.get(key, 1))


def _invalidate(namespace):
    key = CACHE_VERSION_KEYS[namespace]
    cache.add(key, 1, timeout=None)
    return cache.incr(key)


def invalidate_web_analytics():
    return _invalidate("web")


def invalidate_commercial_analytics():
    return _invalidate("commercial")
