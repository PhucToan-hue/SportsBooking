
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import RegisterForm


# ==========================================
# CHUYỂN HƯỚNG THEO VAI TRÒ
# ==========================================

@login_required
def role_redirect_view(request):
    user = request.user

    # Admin hệ thống
    if user.is_superuser:
        return redirect("/admin/")

    # Chủ sân
    if getattr(user, "role", None) == "OWNER":
        return redirect("/owner/dashboard/")

    # Khách hàng
    return redirect("home")


# ==========================================
# ĐĂNG KÝ TÀI KHOẢN
# ==========================================

def register_view(request):
    if request.user.is_authenticated:
        return redirect("role_redirect")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)

            messages.success(
                request,
                "Đăng ký tài khoản thành công!"
            )

            return redirect("role_redirect")
    else:
        form = RegisterForm()

    return render(
        request,
        "accounts/register.html",
        {"form": form}
    )


# ==========================================
# HỒ SƠ NGƯỜI DÙNG
# ==========================================

@login_required
def profile_view(request):
    return render(
        request,
        "accounts/profile.html"
    )


# ==========================================
# ĐĂNG XUẤT
# ==========================================

def logout_view(request):
    if request.method == "POST":
        logout(request)

        messages.success(
            request,
            "Bạn đã đăng xuất thành công!"
        )

        return redirect("home")

    return redirect("home")
