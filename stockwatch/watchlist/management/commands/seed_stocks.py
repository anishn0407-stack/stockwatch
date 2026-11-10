from django.core.management.base import BaseCommand

from watchlist.models import Stock

# A starter list of popular NSE large caps (Yahoo Finance symbols use .NS).
# Index membership and tickers change over time - edit freely, or add any
# other stock with:  python manage.py add_stock SYMBOL.NS "Company name"
STOCKS = [
    ("RELIANCE.NS", "Reliance Industries", "Energy"),
    ("TCS.NS", "Tata Consultancy Services", "IT"),
    ("HDFCBANK.NS", "HDFC Bank", "Banking"),
    ("INFY.NS", "Infosys", "IT"),
    ("ICICIBANK.NS", "ICICI Bank", "Banking"),
    ("HINDUNILVR.NS", "Hindustan Unilever", "FMCG"),
    ("ITC.NS", "ITC", "FMCG"),
    ("SBIN.NS", "State Bank of India", "Banking"),
    ("BHARTIARTL.NS", "Bharti Airtel", "Telecom"),
    ("KOTAKBANK.NS", "Kotak Mahindra Bank", "Banking"),
    ("LT.NS", "Larsen & Toubro", "Infrastructure"),
    ("AXISBANK.NS", "Axis Bank", "Banking"),
    ("BAJFINANCE.NS", "Bajaj Finance", "Financial Services"),
    ("ASIANPAINT.NS", "Asian Paints", "Consumer"),
    ("MARUTI.NS", "Maruti Suzuki", "Auto"),
    ("SUNPHARMA.NS", "Sun Pharmaceutical", "Pharma"),
    ("TITAN.NS", "Titan Company", "Consumer"),
    ("ULTRACEMCO.NS", "UltraTech Cement", "Cement"),
    ("NESTLEIND.NS", "Nestle India", "FMCG"),
    ("WIPRO.NS", "Wipro", "IT"),
    ("HCLTECH.NS", "HCL Technologies", "IT"),
    ("TECHM.NS", "Tech Mahindra", "IT"),
    ("NTPC.NS", "NTPC", "Power"),
    ("POWERGRID.NS", "Power Grid Corporation", "Power"),
    ("ONGC.NS", "Oil & Natural Gas Corp", "Energy"),
    ("COALINDIA.NS", "Coal India", "Mining"),
    ("TATASTEEL.NS", "Tata Steel", "Metals"),
    ("JSWSTEEL.NS", "JSW Steel", "Metals"),
    ("HINDALCO.NS", "Hindalco Industries", "Metals"),
    ("ADANIENT.NS", "Adani Enterprises", "Conglomerate"),
    ("ADANIPORTS.NS", "Adani Ports & SEZ", "Infrastructure"),
    ("BAJAJFINSV.NS", "Bajaj Finserv", "Financial Services"),
    ("DRREDDY.NS", "Dr. Reddy's Laboratories", "Pharma"),
    ("CIPLA.NS", "Cipla", "Pharma"),
    ("EICHERMOT.NS", "Eicher Motors", "Auto"),
    ("HEROMOTOCO.NS", "Hero MotoCorp", "Auto"),
    ("GRASIM.NS", "Grasim Industries", "Cement"),
    ("BRITANNIA.NS", "Britannia Industries", "FMCG"),
    ("INDUSINDBK.NS", "IndusInd Bank", "Banking"),
    ("APOLLOHOSP.NS", "Apollo Hospitals", "Healthcare"),
    ("TATACONSUM.NS", "Tata Consumer Products", "FMCG"),
    ("ETERNAL.NS", "Eternal (Zomato)", "Consumer Tech"),
]


class Command(BaseCommand):
    help = "Load the starter list of NSE stocks into the database."

    def handle(self, *args, **options):
        created = 0
        for symbol, name, sector in STOCKS:
            _, was_created = Stock.objects.update_or_create(
                symbol=symbol, defaults={"name": name, "sector": sector}
            )
            created += was_created
        self.stdout.write(self.style.SUCCESS(f"{len(STOCKS)} stocks ready ({created} new)."))
