
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import RegisterForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)

            messages.success(
                request,
                "Đăng ký tài khoản thành công!"
            )

            return redirect("home")
    else:
        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form}
    )


@login_required
def profile_view(request):
    return render(
        request,
        "accounts/profile.html"
    )


def logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect("home")

    return redirect("home")
