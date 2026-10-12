
from django.urls import path

from . import views


urlpatterns = [
    path(
        "<int:booking_id>/",
        views.payment_detail,
        name="payment_detail"
    ),
    path(
        "<int:booking_id>/submit/",
        views.submit_payment,
        name="submit_payment"
    ),
]
