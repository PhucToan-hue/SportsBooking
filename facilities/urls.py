from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    path(
        "co-so/<int:pk>/",
        views.facility_detail,
        name="facility_detail"
    ),
     path(
        "dat-lich/<int:pk>/",
        views.facility_booking,
        name="facility_booking"
    ),

]