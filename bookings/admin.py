
from django.contrib import admin
from django.utils.html import format_html

from .models import Booking


# =====================================================
# 1. KIỂM TRA QUYỀN ADMIN
# =====================================================

def is_system_admin(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and user.is_superuser
    )


def is_court_owner(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and not user.is_superuser
        and getattr(user, "role", None) == "OWNER"
    )


def can_view_bookings(user):
    return is_system_admin(user) or is_court_owner(user)


# =====================================================
# 2. VIỆT HÓA TÊN MODEL
# =====================================================

Booking._meta.verbose_name = "Đơn đặt sân"
Booking._meta.verbose_name_plural = "Quản lý lịch đặt sân"


# =====================================================
# 3. QUẢN LÝ LỊCH ĐẶT SÂN
# =====================================================

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):

    list_display = (
        "booking_code",
        "customer",
        "court",
        "facility_name",
        "start_time",
        "end_time",
        "total_amount",
        "deposit_amount",
        "display_status",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
        "start_time",
    )

    search_fields = (
        "booking_code",
        "customer__username",
        "customer__full_name",
        "customer__email",
        "court__name",
        "court__facility__name",
    )

    list_select_related = (
        "customer",
        "court__facility",
    )

    ordering = ("-created_at",)

    list_per_page = 20

    readonly_fields = (
        "booking_code",
        "customer",
        "court",
        "start_time",
        "end_time",
        "total_amount",
        "deposit_amount",
        "remaining_amount",
        "status",
        "deposit_deadline",
        "approved_by",
        "approved_at",
        "cancel_reason",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Thông tin đơn đặt sân",
            {
                "fields": (
                    "booking_code",
                    "customer",
                    "court",
                    "start_time",
                    "end_time",
                )
            }
        ),
        (
            "Thông tin thanh toán",
            {
                "fields": (
                    "total_amount",
                    "deposit_amount",
                    "remaining_amount",
                    "deposit_deadline",
                )
            }
        ),
        (
            "Trạng thái đơn",
            {
                "fields": (
                    "status",
                    "approved_by",
                    "approved_at",
                    "cancel_reason",
                )
            }
        ),
        (
            "Thông tin hệ thống",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            }
        ),
    )

    # -------------------------------------------------
    # QUYỀN TRUY CẬP
    # -------------------------------------------------

    def has_module_permission(self, request):
        return can_view_bookings(request.user)

    def has_view_permission(self, request, obj=None):
        if is_system_admin(request.user):
            return True

        if is_court_owner(request.user):
            return (
                obj is None
                or obj.court.facility.owner_id == request.user.pk
            )

        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    # -------------------------------------------------
    # LỌC ĐƠN THEO CHỦ SÂN
    # -------------------------------------------------

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if is_system_admin(request.user):
            return queryset

        if is_court_owner(request.user):
            return queryset.filter(
                court__facility__owner=request.user
            )

        return queryset.none()

    # -------------------------------------------------
    # HIỂN THỊ TÊN CƠ SỞ
    # -------------------------------------------------

    @admin.display(description="Cơ sở")
    def facility_name(self, obj):
        return obj.court.facility.name

    # -------------------------------------------------
    # HIỂN THỊ TRẠNG THÁI
    # -------------------------------------------------

    @admin.display(description="Trạng thái")
    def display_status(self, obj):

        colors = {
            "PENDING_DEPOSIT": "#d97706",
            "PENDING_VERIFICATION": "#d97706",
            "PENDING_APPROVAL": "#2563eb",
            "CONFIRMED": "#16a34a",
            "COMPLETED": "#15803d",
            "CANCELLED": "#6b7280",
            "REJECTED": "#dc2626",
            "EXPIRED": "#6b7280",
        }

        color = colors.get(obj.status, "#6b7280")

        return format_html(
            '<span style="color:{};font-weight:600;">{}</span>',
            color,
            obj.get_status_display()
        )
