from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from . import formatting, services
from .models import Stock, WishlistItem


@override_settings(DEMO_MODE=True)
class StockWatchTests(TestCase):
    def setUp(self):
        cache.clear()
        self.a = Stock.objects.create(symbol="AAA.NS", name="Alpha Ltd", sector="IT")
        self.b = Stock.objects.create(symbol="BBB.NS", name="Beta Ltd", sector="Banking")
        self.c = Stock.objects.create(symbol="CCC.NS", name="Gamma Inc", sector="IT")

    # ---- pages -----------------------------------------------------------
    def test_home_lists_stocks(self):
        res = self.client.get(reverse("home"))
        self.assertContains(res, "Alpha Ltd")
        self.assertContains(res, "Gamma Inc")
        self.assertContains(res, "Demo mode")

    def test_stock_page_shows_price_and_stats(self):
        res = self.client.get(reverse("stock_detail", args=["AAA.NS"]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "52-week high")
        self.assertContains(res, "₹")

    def test_unknown_stock_is_404(self):
        self.assertEqual(self.client.get(reverse("stock_detail", args=["NOPE.NS"])).status_code, 404)

    def test_stock_page_handles_data_failure(self):
        with self.settings(DEMO_MODE=False):
            from unittest import mock

            with mock.patch.object(services, "_fetch_yahoo", side_effect=services.DataUnavailable("No data")):
                res = self.client.get(reverse("stock_detail", args=["AAA.NS"]))
        self.assertContains(res, "Price data is unavailable")

    # ---- API ---------------------------------------------------------------
    def test_history_ranges_shrink(self):
        sizes = {}
        for r in services.RANGES:
            res = self.client.get(reverse("api_history", args=["AAA.NS"]), {"range": r})
            self.assertEqual(res.status_code, 200)
            body = res.json()
            self.assertEqual(len(body["dates"]), len(body["close"]))
            sizes[r] = len(body["dates"])
        self.assertLess(sizes["1M"], sizes["6M"])
        self.assertLess(sizes["6M"], sizes["1Y"])
        self.assertLess(sizes["1Y"], sizes["5Y"])
        self.assertLessEqual(sizes["MAX"], 1500 + 1)

    def test_max_range_covers_whole_history(self):
        body = self.client.get(reverse("api_history", args=["AAA.NS"]), {"range": "MAX"}).json()
        self.assertEqual(body["dates"][0], "2000-01-03")

    def test_history_error_is_502(self):
        from unittest import mock

        with self.settings(DEMO_MODE=False):
            with mock.patch.object(services, "_fetch_yahoo", side_effect=services.DataUnavailable("boom")):
                res = self.client.get(reverse("api_history", args=["AAA.NS"]))
        self.assertEqual(res.status_code, 502)
        self.assertIn("boom", res.json()["error"])

    def test_search(self):
        res = self.client.get(reverse("api_search"), {"q": "gamma"}).json()
        self.assertEqual([r["symbol"] for r in res["results"]], ["CCC.NS"])
        self.assertEqual(self.client.get(reverse("api_search"), {"q": ""}).json(), {"results": []})
        by_sector = self.client.get(reverse("api_search"), {"q": "banking"}).json()
        self.assertEqual([r["symbol"] for r in by_sector["results"]], ["BBB.NS"])

    # ---- wishlist ----------------------------------------------------------
    def test_toggle_adds_then_removes(self):
        url = reverse("api_toggle_wishlist", args=["AAA.NS"])
        self.assertTrue(self.client.post(url).json()["in_wishlist"])
        self.assertTrue(WishlistItem.objects.filter(stock=self.a).exists())
        self.assertFalse(self.client.post(url).json()["in_wishlist"])
        self.assertFalse(WishlistItem.objects.filter(stock=self.a).exists())

    def test_toggle_requires_post(self):
        self.assertEqual(self.client.get(reverse("api_toggle_wishlist", args=["AAA.NS"])).status_code, 405)

    def test_ordering_and_removal(self):
        for s in (self.a, self.b, self.c):
            self.client.post(reverse("api_toggle_wishlist", args=[s.symbol]))
        order = lambda: [i.stock.symbol for i in WishlistItem.objects.all()]
        self.assertEqual(order(), ["AAA.NS", "BBB.NS", "CCC.NS"])
        self.client.post(reverse("wishlist_move", args=["CCC.NS", "up"]))
        self.assertEqual(order(), ["AAA.NS", "CCC.NS", "BBB.NS"])
        self.client.post(reverse("wishlist_move", args=["AAA.NS", "up"]))  # already first: no-op
        self.assertEqual(order(), ["AAA.NS", "CCC.NS", "BBB.NS"])
        self.client.post(reverse("wishlist_move", args=["AAA.NS", "down"]))
        self.assertEqual(order(), ["CCC.NS", "AAA.NS", "BBB.NS"])
        self.client.post(reverse("wishlist_remove", args=["AAA.NS"]))
        self.assertEqual(order(), ["CCC.NS", "BBB.NS"])
        self.assertEqual([i.position for i in WishlistItem.objects.all()], [1, 2])

    def test_wishlist_page_shows_prices_and_empty_state(self):
        self.assertContains(self.client.get(reverse("wishlist")), "Your wishlist is empty")
        self.client.post(reverse("api_toggle_wishlist", args=["BBB.NS"]))
        res = self.client.get(reverse("wishlist"))
        self.assertContains(res, "Beta Ltd")
        self.assertNotContains(res, "Your wishlist is empty")

    def test_wishlist_survives_one_failing_stock(self):
        from unittest import mock

        for s in (self.a, self.b):
            services.wishlist_add(s)
        real = services.get_quote

        def flaky(symbol):
            if symbol == "AAA.NS":
                raise services.DataUnavailable("down")
            return real(symbol)

        with mock.patch.object(services, "get_quote", side_effect=flaky):
            res = self.client.get(reverse("wishlist"))
        self.assertContains(res, "Price unavailable")
        self.assertContains(res, "Beta Ltd")

    # ---- desktop launcher ----------------------------------------------------
    def test_open_desktop_rejects_remote_clients(self):
        res = self.client.post(reverse("open_desktop"), REMOTE_ADDR="203.0.113.9")
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.json()["ok"])


@override_settings(DEMO_MODE=False)
class YahooParsingTests(TestCase):
    """Network is mocked; this checks we parse yfinance's DataFrame shape correctly."""

    def setUp(self):
        cache.clear()

    def _frame(self):
        import pandas as pd

        nan = float("nan")
        idx = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-04"], tz="Asia/Kolkata")
        return pd.DataFrame(
            {
                "Open": [100.123, 101.0, nan],
                "High": [102.999, 103.0, nan],
                "Low": [99.5, 100.0, nan],
                "Close": [100.456, 101.5, nan],
                "Volume": [1000, 0, nan],
                "Dividends": [0.0, 0.0, 0.0],
            },
            index=idx,
        )

    def test_parses_rows_and_drops_nan_days(self):
        from unittest import mock

        fake = mock.Mock()
        fake.history.return_value = self._frame()
        with mock.patch("yfinance.Ticker", return_value=fake) as ticker:
            rows = services.get_full_history("TEST.NS")
        ticker.assert_called_once_with("TEST.NS")
        self.assertEqual([r["date"] for r in rows], ["2024-01-02", "2024-01-03"])
        self.assertEqual(rows[0], {"date": "2024-01-02", "open": 100.12, "high": 103.0, "low": 99.5, "close": 100.46, "volume": 1000})
        self.assertEqual(rows[1]["volume"], 0)

    def test_second_call_uses_cache(self):
        from unittest import mock

        fake = mock.Mock()
        fake.history.return_value = self._frame()
        with mock.patch("yfinance.Ticker", return_value=fake) as ticker:
            services.get_full_history("TEST.NS")
            services.get_full_history("TEST.NS")
        self.assertEqual(ticker.call_count, 1)

    def test_empty_frame_raises_data_unavailable(self):
        import pandas as pd
        from unittest import mock

        fake = mock.Mock()
        fake.history.return_value = pd.DataFrame()
        with mock.patch("yfinance.Ticker", return_value=fake):
            with self.assertRaises(services.DataUnavailable):
                services.get_full_history("BAD.NS")

    def test_market_cap_failure_is_not_fatal(self):
        from unittest import mock

        fake = mock.Mock()
        fake.history.return_value = self._frame()
        type(fake).fast_info = mock.PropertyMock(side_effect=RuntimeError("blocked"))
        with mock.patch("yfinance.Ticker", return_value=fake):
            stats = services.get_stats("TEST.NS")
        self.assertIsNone(stats["market_cap"])
        self.assertEqual(stats["price"], 101.5)


class FormattingTests(TestCase):
    def test_indian_grouping(self):
        self.assertEqual(formatting.money(1234567.5, "₹"), "₹12,34,567.50")
        self.assertEqual(formatting.money(999.5, "₹"), "₹999.50")
        self.assertEqual(formatting.money(100000, "₹"), "₹1,00,000.00")

    def test_us_grouping(self):
        self.assertEqual(formatting.money(1234567.5, "$"), "$1,234,567.50")

    def test_signs(self):
        self.assertEqual(formatting.signed(12.5), "+12.50")
        self.assertEqual(formatting.signed(-3), "−3.00")
        self.assertEqual(formatting.signed_pct(0), "0.00%")
        self.assertEqual(formatting.tone(-1), "down")
        self.assertEqual(formatting.tone(0), "flat")

    def test_market_cap_and_volume(self):
        self.assertEqual(formatting.market_cap(16_00_000 * 1e7, "₹"), "₹16,00,000 Cr")
        self.assertEqual(formatting.market_cap(2.5e12, "$"), "$2.50T")
        self.assertEqual(formatting.market_cap(None), "–")
        self.assertEqual(formatting.volume(1234567), "12,34,567")
