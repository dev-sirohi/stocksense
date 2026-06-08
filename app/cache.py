"""
cache.py - Redis async client, cache helpers, and the cache() decorator.

Role in system: Any route that calls cache_get/cache_set before/after its DB
query gets a Redis-first response path. The decorator pattern keeps caching logic
out of the business logic of individual routes.

Python note: Python decorators are regular functions that accept a function and
return a (usually wrapped) function. They run at definition time when the module
loads, not at call time. C# [Attribute] decorators are metadata baked into
the assembly — they do nothing by themselves until some framework reads them via
reflection. Python decorators actively transform the function, inserting new
behaviour by wrapping it in another function.

Decorator anatomy:
    @cache(ttl=60)          ← cache(ttl=60) executes, returning 'decorator'
    async def my_route():   ← decorator(my_route) executes, returning 'wrapper'
        ...                 ← at request time, 'wrapper' runs instead of my_route
"""

import json
import functools
import hashlib
from contextvars import ContextVar
from typing import Any, Callable, Optional

import redis.asyncio as aioredis
from dotenv import load_dotenv
import os

load_dotenv()

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

# ── TTL constants ─────────────────────────────────────────────────────────────
# Named constants prevent magic numbers scattered through the codebase.
# Python note: module-level constants are UPPER_CASE by convention (PEP 8),
# equivalent to C# public const int.
TTL_STOCK_DATA: int = 60      # stock levels change frequently — short TTL
TTL_SKU_LISTS: int = 300      # SKU metadata rarely changes — longer TTL
TTL_SEARCH_RESULTS: int = 120  # semantic search results
TTL_ALERTS: int = 30          # alerts are time-sensitive

# ── Shared Redis client ───────────────────────────────────────────────────────
# Module-level variable, lazily initialised on first use.
# Python note: Optional[T] means the variable can be either aioredis.Redis or None.
# C# equivalent: private static Redis? _client (nullable reference type).
_redis_client: Optional[aioredis.Redis] = None  # type: ignore[type-arg]

# ── Cache-hit signal ──────────────────────────────────────────────────────────
# ContextVar is a Python mechanism for storing per-coroutine state — similar to
# C# AsyncLocal<T>. Each async "call chain" (one HTTP request) gets its own copy.
# Routes set this to True when they serve from cache; the middleware reads it to
# record whether the request was a cache hit.
#
# Python note: Unlike C# AsyncLocal, ContextVar values set in a CHILD task are
# NOT visible in the parent. We use request.state instead for cross-task signalling
# (see routers/inventory.py). This ContextVar is kept for standalone decorator use.
cache_hit_flag: ContextVar[bool] = ContextVar("cache_hit_flag", default=False)


async def get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    """
    Return (or lazily create) the shared async Redis client.

    Why async: aioredis establishes a TCP connection on first use, which requires
    awaiting. After that, the connection is pooled and reused.
    """
    global _redis_client
    if _redis_client is None:
        # from_url parses redis://host:port/db, redis://user:pass@host:port, etc.
        # decode_responses=True means Redis returns str instead of bytes —
        # easier to work with in Python; C# Redis clients also default to string.
        _redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    """
    Fetch a value from Redis. Returns the deserialised Python object or None on miss.

    Why async: Redis GET is a network call over TCP — awaiting it yields control
    to the event loop so other requests can run while this one waits.
    """
    try:
        client = await get_redis()          # await: ensure connection is ready
        raw = await client.get(key)         # await: network I/O to Redis
        if raw is not None:
            return json.loads(raw)          # deserialise JSON string → Python dict/list
        return None
    except Exception:
        # If Redis is down, silently fall through to the real DB query.
        # This is the graceful degradation pattern — the app still works, just slower.
        return None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    """
    Store a Python object in Redis as JSON with a TTL (time-to-live) in seconds.

    'ex=ttl' instructs Redis to auto-delete the key after ttl seconds.
    Why async: Redis SET is a network write — same reasoning as cache_get.
    """
    try:
        client = await get_redis()
        # json.dumps serialises Python dict/list → JSON string for storage
        # Python note: json.dumps is C# JsonSerializer.Serialize<T>()
        await client.set(key, json.dumps(value), ex=ttl)  # await: network I/O
    except Exception:
        pass  # Redis failure is non-fatal — we just skip caching this response


async def cache_delete_pattern(pattern: str) -> int:
    """
    Delete all Redis keys matching a glob pattern (e.g. 'stock:*').

    Returns the number of deleted keys. Used for cache invalidation when
    underlying data changes (e.g. after receiving new stock).

    Why async: SCAN and DEL are network operations.
    """
    try:
        client = await get_redis()
        keys: list[str] = []
        # scan_iter is a non-blocking cursor scan — preferred over KEYS * which
        # blocks the Redis server for the duration of the scan.
        # Python note: 'async for' iterates an async generator — C# 'await foreach'.
        async for key in client.scan_iter(match=pattern, count=100):
            keys.append(key)
        if keys:
            # *keys unpacks the list as individual arguments — C# params equivalent
            return int(await client.delete(*keys))  # await: network I/O
        return 0
    except Exception:
        return 0


def make_cache_key(prefix: str, **kwargs: Any) -> str:
    """
    Build a deterministic, fixed-length cache key from a prefix and parameters.

    Example:
        make_cache_key("skus", category="Dairy", skip=0, limit=50)
        → "skus:a1b2c3d4"   (8-char MD5 of the sorted JSON params)

    We hash the kwargs so the key length stays constant regardless of
    how many parameters or how long their values are.

    Python note: **kwargs captures all keyword arguments as a dict — equivalent
    to C# params object[] args or Dictionary<string, object> overloads.
    """
    # sort_keys ensures the same dict always produces the same JSON string,
    # regardless of insertion order. Python dicts preserve insertion order since
    # 3.7, but dict literals in different call sites may have different orders.
    param_str = json.dumps(kwargs, sort_keys=True, default=str)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
    return f"{prefix}:{param_hash}"


def cache(ttl: int = TTL_STOCK_DATA, key_prefix: Optional[str] = None) -> Callable:
    """
    Decorator factory that wraps an async function with Redis caching.

    Python note: This is a 'decorator factory' — you call cache(ttl=60) to get
    the actual decorator, which you then apply to a function with @. Three layers:
        1. cache(ttl=60)        → returns 'decorator'
        2. decorator(func)      → returns 'wrapper'
        3. wrapper(*a, **kw)    → runs at call time

    C# comparison: [OutputCache(Duration=60)] is declared once and the ASP.NET
    framework reads it via reflection and handles caching for you. Python decorators
    let YOU write the caching logic — more work, but fully transparent and testable.

    This decorator is best used on non-FastAPI async functions. For FastAPI routes,
    use explicit cache_get/cache_set calls with request.state.cache_hit so FastAPI's
    dependency injection continues to work cleanly. (See routers/inventory.py.)

    Usage:
        @cache(ttl=300, key_prefix="sku_detail")
        async def fetch_sku_detail(sku_id: int, db: AsyncSession) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        # functools.wraps copies __name__, __doc__, __annotations__, __module__,
        # and sets __wrapped__ = func. This preserves the function's identity for
        # FastAPI's OpenAPI schema generation and Python's inspect module.
        # Python note: Without @functools.wraps, your wrapped function would appear
        # as "wrapper" in tracebacks and introspection — very confusing.
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Async wrapper that checks Redis before calling the real function."""
            prefix = key_prefix or func.__name__

            # Build cache key from all keyword arguments, excluding non-serialisable
            # FastAPI internals (db session, request object).
            # Python note: dict comprehension — equivalent to C# LINQ Where/ToDictionary
            serialisable_kwargs = {
                k: v for k, v in kwargs.items()
                if k not in ("db", "request", "redis", "session")
            }
            key = make_cache_key(prefix, **serialisable_kwargs)

            cached = await cache_get(key)
            if cached is not None:
                cache_hit_flag.set(True)
                return cached

            cache_hit_flag.set(False)

            # Cache miss — call the real function with all original arguments
            result = await func(*args, **kwargs)

            # Only cache JSON-serialisable types (dict, list)
            if isinstance(result, (dict, list)):
                await cache_set(key, result, ttl)

            return result

        return wrapper

    return decorator


async def close_redis() -> None:
    """Close the Redis connection pool. Called during application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
