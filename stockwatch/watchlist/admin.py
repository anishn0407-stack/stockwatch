from django.contrib import admin

from .models import Stock, WishlistItem


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("symbol", "name", "sector")
    search_fields = ("symbol", "name", "sector")
    list_filter = ("sector",)


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("stock", "position", "added_at")
    ordering = ("position",)
