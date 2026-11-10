import os
import subprocess
import sys
import tempfile

from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from . import services
from .models import Stock


def _stock_or_404(symbol):
    return get_object_or_404(Stock, symbol=symbol.upper())


def home(request):
    stocks = Stock.objects.select_related("wishlist_item").all()
    sectors = sorted({s.sector for s in stocks if s.sector})
    return render(
        request,
        "watchlist/home.html",
        {"stocks": stocks, "sectors": sectors, "demo": settings.DEMO_MODE},
    )


def stock_detail(request, symbol):
    stock = _stock_or_404(symbol)
    error = stats = None
    try:
        stats = services.get_stats(stock.symbol)
    except Exception as exc:
        error = str(exc)
    return render(
        request,
        "watchlist/stock_detail.html",
        {
            "stock": stock,
            "stats": stats,
            "error": error,
            "in_wishlist": hasattr(stock, "wishlist_item"),
            "ranges": services.RANGES,
            "demo": settings.DEMO_MODE,
        },
    )


def wishlist(request):
    return render(
        request,
        "watchlist/wishlist.html",
        {"rows": services.wishlist_rows(), "demo": settings.DEMO_MODE},
    )


# ---- JSON / action endpoints ------------------------------------------------
@require_GET
def api_search(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return JsonResponse({"results": []})
    matches = Stock.objects.filter(
        Q(name__icontains=q) | Q(symbol__icontains=q) | Q(sector__icontains=q)
    )[:8]
    return JsonResponse(
        {"results": [{"symbol": s.symbol, "name": s.name, "sector": s.sector} for s in matches]}
    )


@require_GET
def api_history(request, symbol):
    stock = _stock_or_404(symbol)
    range_key = request.GET.get("range", "1Y").upper()
    try:
        rows = services.slice_range(services.get_full_history(stock.symbol), range_key)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    return JsonResponse(
        {
            "symbol": stock.symbol,
            "range": range_key,
            "dates": [r["date"] for r in rows],
            "close": [r["close"] for r in rows],
            "volume": [r["volume"] for r in rows],
        }
    )


@require_POST
def api_toggle_wishlist(request, symbol):
    stock = _stock_or_404(symbol)
    if hasattr(stock, "wishlist_item"):
        services.wishlist_remove(stock)
        in_wishlist = False
    else:
        services.wishlist_add(stock)
        in_wishlist = True
    return JsonResponse({"symbol": stock.symbol, "in_wishlist": in_wishlist})


@require_POST
def wishlist_move(request, symbol, direction):
    if direction not in ("up", "down"):
        return JsonResponse({"error": "direction must be up or down"}, status=400)
    services.wishlist_move(_stock_or_404(symbol), direction)
    return redirect("wishlist")


@require_POST
def wishlist_remove(request, symbol):
    services.wishlist_remove(_stock_or_404(symbol))
    return redirect("wishlist")


@require_POST
def open_desktop(request):
    """Launch the tkinter window on the machine running the server.

    Only allowed from the same machine, because it starts a local GUI process.
    """
    if request.META.get("REMOTE_ADDR") not in ("127.0.0.1", "::1"):
        return JsonResponse(
            {"ok": False, "error": "The desktop window can only be opened from the computer running the server."},
            status=403,
        )
    cmd = [sys.executable, str(settings.BASE_DIR / "manage.py"), "desktop"]
    log = tempfile.TemporaryFile()
    # Keep the window alive even if the dev server restarts (different flag per OS).
    detach = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    try:
        proc = subprocess.Popen(
            cmd, cwd=settings.BASE_DIR, stdout=subprocess.DEVNULL, stderr=log, **detach
        )
    except OSError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=500)
    try:
        # If the window crashes right away (for example tkinter is missing),
        # report why instead of silently doing nothing.
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        return JsonResponse({"ok": True})
    log.seek(0)
    reason = log.read().decode(errors="replace").strip().splitlines()
    detail = reason[-1] if reason else f"exit code {proc.returncode}"
    return JsonResponse({"ok": False, "error": f"Desktop window failed to start: {detail}"}, status=500)
