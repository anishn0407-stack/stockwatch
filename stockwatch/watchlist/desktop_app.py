"""Tkinter desktop window for StockWatch.

It uses the SAME Django models, database and price service as the website, so a
stock starred in the browser shows up here and vice versa.

Launch with:   python manage.py desktop
or press "Open desktop window" on the website.
"""
import queue
import threading
import tkinter as tk
from tkinter import ttk

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.dates as mdates  # noqa: E402
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from . import formatting as fmt  # noqa: E402
from . import services  # noqa: E402
from .models import Stock, WishlistItem  # noqa: E402

INK = "#101b2d"
MUTED = "#5b6779"
PAPER = "#f3f5f8"
UP = "#0e7f57"
DOWN = "#be3a34"
SAFFRON = "#e08a00"


class StockWatchApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StockWatch")
        self.geometry("1100x680")
        self.minsize(900, 560)
        self.configure(bg=PAPER)

        self.current = None      # Stock being shown
        self.range_key = "1Y"
        self._load_token = 0     # ignores results from stale background loads
        self._visible = []       # stocks currently listed on the left
        self._results = queue.Queue()

        self._style()
        self._build()
        self._refresh_list()
        self.after(100, self._poll_results)

    # ------------------------------------------------------------------ layout
    def _style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=PAPER)
        style.configure("TLabel", background=PAPER, foreground=INK)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=("TkDefaultFont", 18, "bold"))
        style.configure("Price.TLabel", font=("TkDefaultFont", 26, "bold"))
        style.configure("TButton", padding=(10, 4))
        style.configure("Range.TButton", padding=(10, 3))
        style.configure("Active.Range.TButton", background=INK, foreground="white")
        style.map("Active.Range.TButton", background=[("active", INK)], foreground=[("active", "white")])
        style.configure("Treeview", rowheight=26, background="white", fieldbackground="white")

    def _build(self):
        # Status bar first, so it always keeps its row at the bottom.
        self.status = tk.StringVar()
        ttk.Label(self, textvariable=self.status, style="Muted.TLabel").pack(side="bottom", fill="x", padx=12, pady=(0, 6))

        # Left column: search, tabs, list
        left = ttk.Frame(self, padding=(12, 12, 6, 6))
        left.pack(side="left", fill="y")

        self.search_var = tk.StringVar()
        search = ttk.Entry(left, textvariable=self.search_var, width=32)
        search.pack(fill="x")
        search.insert(0, "")
        self.search_var.trace_add("write", lambda *_: self._refresh_list())
        ttk.Label(left, text="Search by company, symbol or sector", style="Muted.TLabel").pack(anchor="w", pady=(2, 8))

        self.view_var = tk.StringVar(value="all")
        tabs = ttk.Frame(left)
        tabs.pack(fill="x", pady=(0, 6))
        ttk.Radiobutton(tabs, text="All stocks", value="all", variable=self.view_var, command=self._refresh_list).pack(side="left")
        ttk.Radiobutton(tabs, text="Wishlist", value="wishlist", variable=self.view_var, command=self._refresh_list).pack(side="left", padx=(12, 0))

        # Move buttons are packed before the list so they keep their space.
        move = ttk.Frame(left)
        move.pack(side="bottom", fill="x", pady=(8, 0))
        self.up_btn = ttk.Button(move, text="Move up", width=10, command=lambda: self._move("up"))
        self.down_btn = ttk.Button(move, text="Move down", width=10, command=lambda: self._move("down"))
        self.up_btn.pack(side="left")
        self.down_btn.pack(side="left", padx=6)

        box = ttk.Frame(left)
        box.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(box, columns=("star", "name", "sector", "price", "chg"), show="headings", selectmode="browse", height=12)
        self.tree.heading("star", text="")
        self.tree.heading("name", text="Company")
        self.tree.heading("sector", text="Sector")
        self.tree.heading("price", text="Price")
        self.tree.heading("chg", text="Change")
        self.tree.column("star", width=28, anchor="center", stretch=False)
        self.tree.column("name", width=190)
        self.tree.column("sector", width=100)
        self.tree.column("price", width=90, anchor="e")
        self.tree.column("chg", width=70, anchor="e")
        self._show_columns(wishlist=False)
        self.tree.tag_configure("up", foreground=UP)
        self.tree.tag_configure("down", foreground=DOWN)
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Right column: detail
        right = ttk.Frame(self, padding=(6, 12, 12, 6))
        right.pack(side="left", fill="both", expand=True)

        head = ttk.Frame(right)
        head.pack(fill="x")
        titles = ttk.Frame(head)
        titles.pack(side="left", fill="x", expand=True)
        self.title_lbl = ttk.Label(titles, text="Select a stock", style="Title.TLabel")
        self.title_lbl.pack(anchor="w")
        self.sub_lbl = ttk.Label(titles, text="Pick one from the list to see its price history.", style="Muted.TLabel")
        self.sub_lbl.pack(anchor="w")
        self.star_btn = ttk.Button(head, text="Add to wishlist", command=self._toggle_wishlist, state="disabled")
        self.star_btn.pack(side="right")

        price_row = ttk.Frame(right)
        price_row.pack(fill="x", pady=(10, 4))
        self.price_lbl = ttk.Label(price_row, text="", style="Price.TLabel")
        self.price_lbl.pack(side="left")
        self.change_lbl = ttk.Label(price_row, text="")
        self.change_lbl.pack(side="left", padx=12)

        ranges = ttk.Frame(right)
        ranges.pack(fill="x", pady=(0, 6))
        self.range_btns = {}
        for key in services.RANGES:
            btn = ttk.Button(ranges, text="Max" if key == "MAX" else key, width=5, style="Range.TButton", command=lambda k=key: self._set_range(k))
            btn.pack(side="left", padx=(0, 4))
            self.range_btns[key] = btn
        self.range_summary = ttk.Label(ranges, text="", style="Muted.TLabel")
        self.range_summary.pack(side="left", padx=10)
        self._mark_range()

        # The stats line is packed first (at the bottom) so the chart can never push it out of view.
        self.stats_lbl = ttk.Label(right, text="", style="Muted.TLabel", justify="left")
        self.stats_lbl.pack(side="bottom", anchor="w", pady=(8, 0))

        self.figure = Figure(figsize=(5, 2.6), dpi=100, facecolor="white")
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=right)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._draw_message("Select a stock to see its chart.")
        self._update_buttons()

    # ------------------------------------------------------------------- list
    def _show_columns(self, wishlist):
        # "All stocks" shows sectors; the wishlist shows live prices instead.
        self.tree.configure(displaycolumns=("star", "name", "price", "chg") if wishlist else ("star", "name", "sector"))

    def _refresh_list(self):
        query = self.search_var.get().strip().lower()
        wishlist_view = self.view_var.get() == "wishlist"
        self._show_columns(wishlist_view)
        if wishlist_view:
            stocks = [item.stock for item in WishlistItem.objects.select_related("stock")]
        else:
            stocks = list(Stock.objects.all())
        if query:
            stocks = [s for s in stocks if query in s.name.lower() or query in s.symbol.lower() or query in s.sector.lower()]
        starred = set(WishlistItem.objects.values_list("stock_id", flat=True))
        self._visible = stocks

        self.tree.delete(*self.tree.get_children())
        for s in stocks:
            price = chg = ""
            tags = ()
            if wishlist_view:  # only the (short) wishlist shows prices, to avoid 40 network calls
                try:
                    q = services.get_quote(s.symbol)
                    price, chg = fmt.money(q["price"], s.currency), fmt.signed_pct(q["change_pct"])
                    tags = (fmt.tone(q["change"]),)
                except Exception:
                    price = "n/a"
            self.tree.insert("", "end", iid=str(s.pk), values=("★" if s.pk in starred else "", s.name, s.sector, price, chg), tags=tags)
        if self.current and str(self.current.pk) in self.tree.get_children():
            self.tree.selection_set(str(self.current.pk))
            self.tree.see(str(self.current.pk))
        self._update_buttons()

    def _on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        stock = next((s for s in self._visible if str(s.pk) == sel[0]), None)
        if stock and (self.current is None or stock.pk != self.current.pk):
            self.current = stock
            self._show_stock()
        self._update_buttons()

    # ----------------------------------------------------------------- detail
    def _show_stock(self):
        s = self.current
        self.title_lbl.config(text=s.name)
        self.sub_lbl.config(text=f"{s.symbol}   {s.sector}".strip())
        self._sync_star()
        self.price_lbl.config(text="")
        self.change_lbl.config(text="")
        self.stats_lbl.config(text="")
        self.range_summary.config(text="")
        self._draw_message("Loading price history…")
        self._load_history()

    def _set_range(self, key):
        self.range_key = key
        self._mark_range()
        if self.current:
            self._load_history()

    def _mark_range(self):
        for key, btn in self.range_btns.items():
            btn.configure(style="Active.Range.TButton" if key == self.range_key else "Range.TButton")

    def _load_history(self):
        """Fetch on a worker thread so the window never freezes on a slow network."""
        self._load_token += 1
        token, stock, key = self._load_token, self.current, self.range_key
        self.status.set("Loading…")

        def work():
            # Worker threads never touch Tk widgets; they hand results to the
            # main thread through a queue that _poll_results drains.
            try:
                rows = services.get_full_history(stock.symbol)
                shown = services.slice_range(rows, key)
                stats = services.get_stats(stock.symbol)
                result = (shown, stats, None)
            except Exception as exc:
                result = (None, None, str(exc))
            self._results.put((token, stock, key) + result)

        threading.Thread(target=work, daemon=True).start()

    def _poll_results(self):
        try:
            while True:
                self._on_loaded(*self._results.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll_results)

    def _on_loaded(self, token, stock, key, rows, stats, error):
        if token != self._load_token:
            return  # user already clicked something else
        self.status.set("")
        if error:
            self._draw_message(f"Price data is unavailable.\n{error}")
            return
        cur = stock.currency
        self.price_lbl.config(text=fmt.money(stats["price"], cur))
        self.change_lbl.config(
            text=f"{fmt.signed(stats['change'], cur)} ({fmt.signed_pct(stats['change_pct'])})",
            foreground={"up": UP, "down": DOWN}.get(fmt.tone(stats["change"]), MUTED),
        )
        self.stats_lbl.config(
            text=(
                f"Open {fmt.money(stats['open'], cur)}    High {fmt.money(stats['high'], cur)}    Low {fmt.money(stats['low'], cur)}    "
                f"Volume {fmt.volume(stats['volume'])}\n"
                f"52-week range {fmt.money(stats['week52_low'], cur)} – {fmt.money(stats['week52_high'], cur)}    "
                f"Market cap {fmt.market_cap(stats['market_cap'], cur)}    History starts {stats['first_date']}"
            )
        )
        self._draw_chart(rows, cur)

    # ------------------------------------------------------------------ chart
    def _draw_message(self, text):
        self.ax.clear()
        self.ax.axis("off")
        self.ax.text(0.5, 0.5, text, ha="center", va="center", color=MUTED, transform=self.ax.transAxes, wrap=True)
        self.canvas.draw_idle()

    def _draw_chart(self, rows, currency):
        from datetime import date

        dates = [date.fromisoformat(r["date"]) for r in rows]
        closes = [r["close"] for r in rows]
        color = UP if closes[-1] >= closes[0] else DOWN
        pct = (closes[-1] - closes[0]) / closes[0] * 100
        label = "all time" if self.range_key == "MAX" else self.range_key
        self.range_summary.config(text=f"{fmt.signed_pct(pct)} over {label}")

        ax = self.ax
        ax.clear()
        ax.axis("on")
        ax.plot(dates, closes, color=color, linewidth=1.6)
        ax.fill_between(dates, closes, min(closes), color=color, alpha=0.10)
        ax.set_facecolor("white")
        for side in ("top", "left"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color("#dce2ea")
        ax.spines["right"].set_color("#dce2ea")
        ax.yaxis.tick_right()
        ax.grid(axis="y", color="#dce2ea", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=MUTED, labelsize=8, length=0)
        decimals = 0 if (max(closes) - min(closes)) >= 10 else 2
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _pos: fmt.number(v, decimals, currency)))
        locator = mdates.AutoDateLocator(minticks=3, maxticks=6)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.margins(x=0.01)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    # --------------------------------------------------------------- wishlist
    def _sync_star(self):
        if not self.current:
            return
        on = WishlistItem.objects.filter(stock=self.current).exists()
        self.star_btn.config(text="★ In your wishlist" if on else "☆ Add to wishlist", state="normal")

    def _toggle_wishlist(self):
        if not self.current:
            return
        stock = Stock.objects.get(pk=self.current.pk)
        if hasattr(stock, "wishlist_item"):
            services.wishlist_remove(stock)
            self.status.set("Removed from wishlist.")
        else:
            services.wishlist_add(stock)
            self.status.set("Added to wishlist.")
        self._sync_star()
        self._refresh_list()

    def _move(self, direction):
        if not self.current or self.view_var.get() != "wishlist":
            return
        services.wishlist_move(Stock.objects.get(pk=self.current.pk), direction)
        self._refresh_list()

    def _update_buttons(self):
        can_move = self.view_var.get() == "wishlist" and self.current is not None and WishlistItem.objects.filter(stock=self.current).exists()
        state = "normal" if can_move else "disabled"
        self.up_btn.config(state=state)
        self.down_btn.config(state=state)


def run():
    app = StockWatchApp()
    app.mainloop()
