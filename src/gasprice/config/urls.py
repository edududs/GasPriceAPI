from django.urls import path

from gasprice.prices.adapters import views
from gasprice.prices.adapters.api import api
from gasprice.trips.adapters import views as trips

urlpatterns = [
    path("", views.index, name="index"),
    path("board/<str:fuel>/", views.board, name="board"),
    path("states/<str:state>/", views.state_detail, name="state"),
    path("trip/", trips.trip_page, name="trip"),
    path("trip/vehicles/", trips.vehicle_search, name="trip-vehicles"),
    path("trip/places/", trips.place_search, name="trip-places"),
    path("trip/estimate/", trips.trip_estimate, name="trip-estimate"),
    path("api/v1/", api.urls),
]
