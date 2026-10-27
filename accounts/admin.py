
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.db.models import Q
from .models import User, OwnerProfile, Customer, CourtOwner

from .models import User, OwnerProfile


# =====================================================
# ADMIN CHUNG - QUẢN LÝ TÀI KHOẢN
# =====================================================

class BaseAccountAdmin(UserAdmin):

    list_display = (
        "username",
        "full_name",
        "email",
        "phone",
        "display_role",
        "account_status",
        "lock_unlock_button",
    )

    list_filter = (
        "is_active",
        "date_joined",
    )

    search_fields = (
        "username",
        "full_name",
        "email",
        "phone",
    )

    ordering = ("-date_joined",)

    list_per_page = 20

    readonly_fields = (
        "date_joined",
        "last_login",
        "account_status",
    )

    fieldsets = (
        (
            "Thông tin tài khoản",
            {
                "fields": (
                    "username",
                    "password",
                    "full_name",
                    "email",
                    "phone",
                )
            },
        ),
        (
            "Phân quyền và trạng thái",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Thông tin hoạt động",
            {
                "fields": (
                    "account_status",
                    "last_login",
                    "date_joined",
                )
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Thông tin bổ sung",
            {
                "fields": (
                    "email",
                    "full_name",
                    "phone",
                    "role",
                )
            },
        ),
    )

    actions = [
        "lock_accounts",
        "unlock_accounts",
    ]

    @admin.display(description="Loại tài khoản")
    def display_role(self, obj):
        return obj.get_role_display()

    @admin.display(
        description="Trạng thái",
        boolean=True
    )
    def account_status(self, obj):
        return obj.is_active

    @admin.display(description="Thao tác")
    def lock_unlock_button(self, obj):
        if obj.is_active:
            return "🔒 Có thể khóa"
        return "🔓 Có thể mở khóa"

    @admin.action(description="🔒 Khóa các tài khoản đã chọn")
    def lock_accounts(self, request, queryset):

        queryset = queryset.exclude(
            pk=request.user.pk
        ).exclude(
            is_superuser=True
        )

        count = queryset.update(is_active=False)

        self.message_user(
            request,
            f"Đã khóa {count} tài khoản.",
            messages.SUCCESS
        )

    @admin.action(description="🔓 Mở khóa các tài khoản đã chọn")
    def unlock_accounts(self, request, queryset):

        queryset = queryset.exclude(
            is_superuser=True
        )

        count = queryset.update(is_active=True)

        self.message_user(
            request,
            f"Đã mở khóa {count} tài khoản.",
            messages.SUCCESS
        )

    def save_model(self, request, obj, form, change):

        if change:
            if obj.pk == request.user.pk and not obj.is_active:
                obj.is_active = True
                self.message_user(
                    request,
                    "Không thể khóa chính tài khoản đang đăng nhập.",
                    messages.WARNING
                )

        super().save_model(
            request,
            obj,
            form,
            change
        )


# =====================================================
# ADMIN - NGƯỜI DÙNG / QUẢN TRỊ
# =====================================================

@admin.register(User)
class CustomUserAdmin(BaseAccountAdmin):

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            Q(role=User.Role.ADMIN)
            | Q(is_superuser=True)
        )


# =====================================================
# ADMIN - KHÁCH HÀNG
# =====================================================


@admin.register(Customer)
class CustomerAdmin(BaseAccountAdmin):

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            role=User.Role.CUSTOMER,
            is_superuser=False
        )

    def save_model(self, request, obj, form, change):
        obj.role = User.Role.CUSTOMER
        obj.is_staff = False
        obj.is_superuser = False
        super().save_model(request, obj, form, change)


# =====================================================
# ADMIN - QUẢN LÝ SÂN
# =====================================================

@admin.register(CourtOwner)
class CourtOwnerAdmin(BaseAccountAdmin):

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            role=User.Role.OWNER,
            is_superuser=False
        )

    def save_model(self, request, obj, form, change):
        obj.role = User.Role.OWNER
        obj.is_staff = False
        obj.is_superuser = False
        super().save_model(request, obj, form, change)


# =====================================================
# ADMIN - HỒ SƠ CHỦ SÂN
# =====================================================

@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "business_name",
        "verification_status",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__full_name",
        "business_name",
    )

    list_filter = (
        "verification_status",
    )
