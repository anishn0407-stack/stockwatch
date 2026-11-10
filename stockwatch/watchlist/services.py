"""Data layer shared by the Django website AND the tkinter desktop window.

Neither UI talks to Yahoo Finance directly; both call the functions here, so
the two front-ends always show the same numbers.
"""
import hashlib
import math
import random
from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Max

RANGES = ["1M", "6M", "1Y", "5Y", "MAX"]
_RANGE_DAYS = {"1M": 31, "6M": 183, "1Y": 366, "5Y": 366 * 5}
_MAX_POINTS = 1500  # keep chart payloads small for very long histories


class DataUnavailable(Exception):
    """Raised when price data can't be fetched for a symbol."""


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------
def _fetch_yahoo(symbol):
    import yfinance as yf

    df = yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=False)
    if df is None or df.empty:
        raise DataUnavailable(f"No price data returned for {symbol}.")
    rows = []
    for ts, r in df.iterrows():
        if r["Close"] != r["Close"]:  # NaN
            continue
        rows.append(
            {
                "date": ts.strftime("%Y-%m-%d"),
                "open": round(float(r["Open"]), 2),
                "high": round(float(r["High"]), 2),
                "low": round(float(r["Low"]), 2),
                "close": round(float(r["Close"]), 2),
                "volume": int(r["Volume"]) if r["Volume"] == r["Volume"] else 0,
            }
        )
    if not rows:
        raise DataUnavailable(f"No price data returned for {symbol}.")
    return rows


def _fetch_demo(symbol):
    """Deterministic fake price history (geometric random walk) per symbol."""
    seed = int(hashlib.sha256(symbol.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    price = rng.uniform(80, 3000)
    start, end = date(2000, 1, 3), date.today()
    rows, d = [], start
    while d <= end:
        if d.weekday() < 5:
            ret = rng.gauss(0.00025, 0.014)
            o = price
            c = max(1.0, o * math.exp(ret))
            hi = max(o, c) * (1 + abs(rng.gauss(0, 0.006)))
            lo = min(o, c) * (1 - abs(rng.gauss(0, 0.006)))
            rows.append(
                {
                    "date": d.isoformat(),
                    "open": round(o, 2),
                    "high": round(hi, 2),
                    "low": round(lo, 2),
                    "close": round(c, 2),
                    "volume": int(rng.uniform(2e5, 9e6)),
                }
            )
            price = c
        d += timedelta(days=1)
    return rows


def get_full_history(symbol):
    """Entire daily history for `symbol` (cached). Oldest row first."""
    key = f"hist:{'demo' if settings.DEMO_MODE else 'live'}:{symbol}"
    rows = cache.get(key)
    if rows is None:
        rows = _fetch_demo(symbol) if settings.DEMO_MODE else _fetch_yahoo(symbol)
        cache.set(key, rows, settings.PRICE_CACHE_SECONDS)
    return rows


# --------------------------------------------------------------------------
# Shaping data for the UIs
# --------------------------------------------------------------------------
def slice_range(rows, range_key):
    """Return the part of `rows` for a range button (1M, 6M, 1Y, 5Y, MAX)."""
    if range_key not in RANGES:
        range_key = "1Y"
    if range_key != "MAX" and rows:
        last = date.fromisoformat(rows[-1]["date"])
        cutoff = (last - timedelta(days=_RANGE_DAYS[range_key])).isoformat()
        rows = [r for r in rows if r["date"] >= cutoff]
    if len(rows) > _MAX_POINTS:
        step = math.ceil(len(rows) / _MAX_POINTS)
        sampled = rows[::step]
        if sampled[-1] is not rows[-1]:
            sampled.append(rows[-1])
        rows = sampled
    return rows


def get_quote(symbol):
    """Latest close + day change, derived from the cached history."""
    rows = get_full_history(symbol)
    last = rows[-1]
    prev = rows[-2]["close"] if len(rows) > 1 else last["close"]
    change = last["close"] - prev
    pct = (change / prev * 100) if prev else 0.0
    return {
        "price": last["close"],
        "change": round(change, 2),
        "change_pct": round(pct, 2),
        "as_of": last["date"],
    }


def get_stats(symbol):
    """Key stats for the stock page."""
    rows = get_full_history(symbol)
    last = rows[-1]
    year = rows[-252:]
    stats = get_quote(symbol)
    stats.update(
        {
            "open": last["open"],
            "high": last["high"],
            "low": last["low"],
            "volume": last["volume"],
            "week52_high": max(r["high"] for r in year),
            "week52_low": min(r["low"] for r in year),
            "first_date": rows[0]["date"],
            "market_cap": _market_cap(symbol),
        }
    )
    return stats


def _market_cap(symbol):
    if settings.DEMO_MODE:
        return None
    key = f"mcap:{symbol}"
    if key in cache:
        return cache.get(key)
    try:
        import yfinance as yf

        value = yf.Ticker(symbol).fast_info["market_cap"]
        value = int(value) if value else None
    except Exception:
        value = None
    cache.set(key, value, settings.PRICE_CACHE_SECONDS)
    return value


# --------------------------------------------------------------------------
# Wishlist operations (used by both UIs)
# --------------------------------------------------------------------------
def wishlist_add(stock):
    from .models import WishlistItem

    if hasattr(stock, "wishlist_item"):
        return stock.wishlist_item, False
    next_pos = (WishlistItem.objects.aggregate(m=Max("position"))["m"] or 0) + 1
    return WishlistItem.objects.create(stock=stock, position=next_pos), True


def wishlist_remove(stock):
    from .models import WishlistItem

    WishlistItem.objects.filter(stock=stock).delete()
    _renumber()


def wishlist_move(stock, direction):
    """Move a wishlist item 'up' or 'down' one place."""
    from .models import WishlistItem

    items = list(WishlistItem.objects.all())
    idx = next((i for i, it in enumerate(items) if it.stock_id == stock.id), None)
    if idx is None:
        return
    swap = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap < len(items):
        items[idx], items[swap] = items[swap], items[idx]
        for pos, it in enumerate(items, start=1):
            if it.position != pos:
                it.position = pos
                it.save(update_fields=["position"])


def _renumber():
    from .models import WishlistItem

    for pos, it in enumerate(WishlistItem.objects.all(), start=1):
        if it.position != pos:
            it.position = pos
            it.save(update_fields=["position"])


def wishlist_rows():
    """Wishlist with live prices. Per-stock failures don't break the list."""
    from .models import WishlistItem

    out = []
    for item in WishlistItem.objects.select_related("stock"):
        try:
            quote = get_quote(item.stock.symbol)
            error = None
        except Exception as exc:  # network hiccup etc.
            quote, error = None, str(exc)
        out.append({"stock": item.stock, "quote": quote, "error": error})
    return out
