
from django.urls import path

from . import views
from . import owner_booking
from . import booking_approval

app_name = "owner_dashboard"

urlpatterns = [
    # ==========================================
    # DASHBOARD CHỦ SÂN
    # ==========================================
    path(
        "dashboard/",
        views.dashboard_view,
        name="dashboard",
    ),

    # ==========================================
    # LỊCH SÂN
    # Giữ nguyên xem lịch quá khứ, hiện tại,
    # tương lai và nhập khách vãng lai
    # ==========================================
    path(
        "schedule/",
        views.schedule_view,
        name="schedule",
    ),

    # ==========================================
    # QUẢN LÝ CƠ SỞ
    # ==========================================
    path(
        "facilities/",
        views.facility_list_view,
        name="facility_list",
    ),

    # ==========================================
    # QUẢN LÝ SÂN
    # ==========================================
    path(
        "courts/",
        views.court_list_view,
        name="court_list",
    ),

    # Thêm sân mới
    path(
        "courts/add/",
        views.court_add_view,
        name="court_add",
    ),

    # Sửa thông tin sân
    path(
        "courts/<int:court_id>/edit/",
        views.court_edit_view,
        name="court_edit",
    ),

    # Xóa sân
    path(
        "courts/<int:court_id>/delete/",
        views.court_delete_view,
        name="court_delete",
    ),

    # Khóa toàn sân / mở hoạt động
    path(
        "courts/<int:court_id>/status/",
        views.court_status_view,
        name="court_status",
    ),

    # Quản lý bảng giá
    path(
        "courts/<int:court_id>/prices/",
        views.court_price_manage_view,
        name="court_price_manage",
    ),

    # Khóa giờ / mở khóa giờ
    path(
        "courts/<int:court_id>/blocks/",
        views.court_block_manage_view,
        name="court_block_manage",
    ),

    # ==========================================
    # DANH SÁCH ĐƠN ĐẶT SÂN
    # ==========================================
    path(
        "bookings/",
        views.booking_list_view,
        name="booking_list",
    ),

    # ==========================================
    # ĐẶT SÂN TRỰC TIẾP TẠI QUẦY
    # GIỮ NGUYÊN
    # ==========================================
    path(
        "booking-confirm/",
        owner_booking.owner_booking_confirm,
        name="booking_confirm",
    ),

    # ==========================================
    # DUYỆT ĐƠN ONLINE
    # GIỮ NGUYÊN
    # ==========================================
    path(
        "booking-approvals/",
        booking_approval.booking_approvals_view,
        name="booking_approvals",
    ),

    # ==========================================
    # DUYỆT / TỪ CHỐI / XÁC MINH TIỀN
    # GIỮ NGUYÊN
    # ==========================================
    path(
        "booking-approvals/<int:booking_id>/action/",
        booking_approval.booking_approval_action,
        name="booking_approval_action",
    ),
]
