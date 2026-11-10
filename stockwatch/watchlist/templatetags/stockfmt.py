from django import template

from .. import formatting as f

register = template.Library()


@register.filter
def money(value, currency="₹"):
    return f.money(value, currency)


@register.filter
def signed(value, currency="₹"):
    return f.signed(value, currency)


@register.filter
def signed_pct(value):
    return f.signed_pct(value)


@register.filter
def volume(value):
    return f.volume(value)


@register.filter
def market_cap(value, currency="₹"):
    return f.market_cap(value, currency)


@register.filter
def tone(value):
    return f.tone(value)
