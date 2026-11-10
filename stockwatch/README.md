# StockWatch

A simple stock wishlist, built with **Django** (website) and **tkinter** (desktop window).
Browse NSE stocks, open one to see its full price history, and star it to save it to your wishlist.

- **Website:** search with autocomplete, stock page with a price chart (1M, 6M, 1Y, 5Y, Max) and key stats, wishlist page with latest prices, reordering and removal.
- **Desktop window:** the same wishlist and charts in a tkinter app. It uses the same Django models, database and price service as the website, so a star added in one shows up in the other.

## Run it

You need Python 3.10 or newer, and tkinter for the desktop window (it comes with the python.org installers for Windows and macOS; on Ubuntu/Debian run `sudo apt install python3-tk`).

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_stocks
python manage.py runserver
```

Open http://127.0.0.1:8000. Click **Open desktop window** in the top bar to launch the tkinter app, or run it directly:

```bash
python manage.py desktop
```

### Demo mode (no internet needed)

Prices come from Yahoo Finance through `yfinance`. If you are offline, or Yahoo is rate-limiting you, generated prices keep everything usable:

```bash
# macOS/Linux
STOCKWATCH_DEMO=1 python manage.py runserver
# Windows PowerShell
$env:STOCKWATCH_DEMO=1; python manage.py runserver
```

The site shows a yellow "Demo mode" bar when this is on. Demo prices are random and not real.

## Adding stocks

`seed_stocks` loads about 40 popular NSE large caps. The list is a starting point, not an exact index, and tickers change over time, so edit `watchlist/management/commands/seed_stocks.py` if one looks wrong. To add any other Yahoo Finance symbol:

```bash
python manage.py add_stock PIDILITIND.NS "Pidilite Industries" --sector Chemicals
```

Symbols ending in `.NS` or `.BO` display in rupees; anything else displays in dollars (for example `AAPL`).

## How the pieces fit

```
watchlist/
  models.py        Stock, WishlistItem
  services.py      price history (Yahoo or demo), caching, stats, wishlist operations
  formatting.py    number formatting (Indian digit grouping), used by both UIs
  views.py         pages + small JSON endpoints (search, history, star)
  templates/       base, home, stock detail, wishlist
  static/          style.css, app.js (stars, search), pricechart.js (canvas chart)
  desktop_app.py   the tkinter window
  management/commands/   seed_stocks, add_stock, desktop
```

Both front-ends call `services.py`, so there is one place that fetches and shapes data. Full price history is fetched once per stock and cached for 30 minutes (`PRICE_CACHE_SECONDS` in `config/settings.py`); the chart ranges are sliced from that.

## Good to know

- `yfinance` is an unofficial wrapper around Yahoo Finance. It can break or rate-limit without notice, which is why the pages show a clear message instead of crashing when data can't be fetched.
- The first time you open the wishlist, each stock's history is fetched once, so a long wishlist loads slowly on that first visit.
- **Open desktop window** only works when the browser and the server are on the same computer, because it starts a window on the machine running Django.
- The wishlist is shared by everyone who opens the site: there are no user accounts. Login is a natural next feature.

## Tests

```bash
python manage.py test watchlist
```
