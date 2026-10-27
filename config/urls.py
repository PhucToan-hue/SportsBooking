
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


# ==========================================
# CẤU HÌNH GIAO DIỆN DJANGO ADMIN
# ==========================================

admin.site.site_header = (
    "HỆ THỐNG QUẢN LÝ VÀ ĐẶT SÂN THỂ THAO"
)

admin.site.site_title = "Quản lý sân thể thao"

admin.site.index_title = "TRANG QUẢN TRỊ HỆ THỐNG"


# ==========================================
# KHAI BÁO ĐƯỜNG DẪN
# ==========================================

urlpatterns = [

    # Admin hệ thống
    path(
        "admin/",
        admin.site.urls
    ),

    # Đăng nhập, đăng ký, tài khoản
    path(
        "accounts/",
        include("accounts.urls")
    ),

    # Thanh toán VietQR
    path(
        "payments/",
        include("payments.urls")
    ),

    # Dashboard quản lý dành cho chủ sân
    path(
        "owner/",
        include("owner_dashboard.urls")
    ),

    # Trang chủ, danh sách cơ sở, đặt sân
    path(
        "",
        include("facilities.urls")
    ),
]


# ==========================================
# HIỂN THỊ FILE MEDIA KHI DEBUG
# ==========================================

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
