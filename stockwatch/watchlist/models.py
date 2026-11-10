from django.db import models


class Stock(models.Model):
    """A tradable stock that can be browsed and added to the wishlist."""

    symbol = models.CharField(max_length=20, unique=True, help_text="Yahoo Finance symbol, e.g. RELIANCE.NS")
    name = models.CharField(max_length=120)
    sector = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.symbol})"

    @property
    def currency(self):
        return "₹" if self.symbol.endswith((".NS", ".BO")) else "$"

    @property
    def short_symbol(self):
        """RELIANCE.NS -> RELIANCE"""
        return self.symbol.split(".")[0]


class WishlistItem(models.Model):
    """A stock the user has saved. `position` controls manual ordering."""

    stock = models.OneToOneField(Stock, on_delete=models.CASCADE, related_name="wishlist_item")
    position = models.PositiveIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "added_at"]

    def __str__(self):
        return f"#{self.position} {self.stock.symbol}"
