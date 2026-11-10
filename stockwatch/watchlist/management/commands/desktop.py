from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Open the StockWatch tkinter desktop window (shares the website's database)."

    def handle(self, *args, **options):
        try:
            import tkinter  # noqa: F401
        except ImportError:
            raise CommandError(
                "tkinter is not installed for this Python. On Ubuntu/Debian run "
                "'sudo apt install python3-tk'; on macOS use the python.org installer or "
                "'brew install python-tk'."
            )
        from watchlist.desktop_app import run

        run()
