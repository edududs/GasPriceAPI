from django.urls import path

from gasprice.prices.adapters import views
from gasprice.prices.adapters.api import api

urlpatterns = [
    path("", views.index, name="index"),
    path("board/<str:fuel>/", views.board, name="board"),
    path("states/<str:state>/", views.state_detail, name="state"),
    path("api/v1/", api.urls),
]
