
from django.urls import path
from django.contrib.auth import views as auth_views

from . import views


urlpatterns = [
    path(
        "register/",
        views.register_view,
        name="register"
    ),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="accounts/login.html",
            redirect_authenticated_user=True,
            next_page="role_redirect",
        ),
        name="login"
    ),

    path(
        "redirect/",
        views.role_redirect_view,
        name="role_redirect"
    ),

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),

    path(
        "profile/",
        views.profile_view,
        name="profile"
    ),
]
