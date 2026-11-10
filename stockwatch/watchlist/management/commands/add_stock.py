from django.core.management.base import BaseCommand, CommandError

from watchlist.models import Stock
from watchlist.services import DataUnavailable, get_full_history


class Command(BaseCommand):
    help = 'Add any Yahoo Finance symbol, e.g.  add_stock PIDILITIND.NS "Pidilite Industries"'

    def add_arguments(self, parser):
        parser.add_argument("symbol")
        parser.add_argument("name", nargs="?", default="")
        parser.add_argument("--sector", default="")
        parser.add_argument("--skip-check", action="store_true", help="Don't verify the symbol with Yahoo first")

    def handle(self, *args, **opts):
        symbol = opts["symbol"].upper()
        if not opts["skip_check"]:
            try:
                get_full_history(symbol)
            except DataUnavailable as exc:
                raise CommandError(str(exc))
            except Exception as exc:
                raise CommandError(f"Could not verify {symbol}: {exc} (use --skip-check to add anyway)")
        stock, created = Stock.objects.update_or_create(
            symbol=symbol,
            defaults={"name": opts["name"] or symbol, "sector": opts["sector"]},
        )
        self.stdout.write(self.style.SUCCESS(f"{'Added' if created else 'Updated'} {stock}"))
