"""Number formatting shared by the Django templates and the tkinter window."""

MINUS = "−"  # a real minus sign reads better next to digits than a hyphen


def _group(int_str, indian):
    if len(int_str) <= 3:
        return int_str
    if not indian:
        return f"{int(int_str):,}"
    head, tail = int_str[:-3], int_str[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def number(value, decimals=2, currency="₹"):
    """1234567.5 -> 12,34,567.50 for rupees, 1,234,567.50 for dollars."""
    if value is None:
        return "–"
    text = f"{abs(float(value)):.{decimals}f}"
    int_part, _, frac = text.partition(".")
    out = _group(int_part, indian=(currency == "₹"))
    return f"{out}.{frac}" if frac else out


def money(value, currency="₹"):
    if value is None:
        return "–"
    return f"{currency}{number(value, 2, currency)}"


def signed(value, currency="₹", decimals=2):
    if value is None:
        return "–"
    sign = "+" if value > 0 else MINUS if value < 0 else ""
    return f"{sign}{number(value, decimals, currency)}"


def signed_pct(value):
    if value is None:
        return "–"
    sign = "+" if value > 0 else MINUS if value < 0 else ""
    return f"{sign}{abs(value):.2f}%"


def volume(value):
    if value is None:
        return "–"
    return _group(str(int(value)), indian=True)


def market_cap(value, currency="₹"):
    if not value:
        return "–"
    if currency == "₹":
        crore = value / 1e7
        return f"₹{number(crore, 0, currency)} Cr"
    for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if value >= limit:
            return f"${value / limit:.2f}{suffix}"
    return f"${number(value, 0, currency)}"


def tone(value):
    if value is None or value == 0:
        return "flat"
    return "up" if value > 0 else "down"
