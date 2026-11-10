from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("stock/<str:symbol>/", views.stock_detail, name="stock_detail"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/move/<str:symbol>/<str:direction>/", views.wishlist_move, name="wishlist_move"),
    path("wishlist/remove/<str:symbol>/", views.wishlist_remove, name="wishlist_remove"),
    path("api/search/", views.api_search, name="api_search"),
    path("api/history/<str:symbol>/", views.api_history, name="api_history"),
    path("api/wishlist/toggle/<str:symbol>/", views.api_toggle_wishlist, name="api_toggle_wishlist"),
    path("desktop/open/", views.open_desktop, name="open_desktop"),
]
