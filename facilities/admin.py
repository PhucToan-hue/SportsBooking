
from django.contrib import admin, messages
from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q

from .models import (
    Facility,
    Amenity,
    FacilityAmenity,
    FacilityBankAccount,
)


# =====================================================
# 1. PHÂN BIỆT ADMIN HỆ THỐNG VÀ ADMIN CHỦ SÂN
# =====================================================

def is_system_admin(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and (
            user.is_superuser
            or user.role == "ADMIN"
        )
    )


def is_court_owner(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.is_staff
        and user.role == "OWNER"
        and not user.is_superuser
    )


def can_manage_facilities(user):
    return is_system_admin(user) or is_court_owner(user)


def owned_facilities(user):
    return Facility.objects.filter(owner=user)


# =====================================================
# 2. VIỆT HÓA TÊN HIỂN THỊ
# =====================================================

Facility._meta.verbose_name = "Cơ sở thể thao"
Facility._meta.verbose_name_plural = "Danh sách cơ sở thể thao"

Amenity._meta.verbose_name = "Tiện ích"
Amenity._meta.verbose_name_plural = "Danh sách tiện ích"

FacilityAmenity._meta.verbose_name = "Tiện ích cơ sở"
FacilityAmenity._meta.verbose_name_plural = "Tiện ích của cơ sở"

FacilityBankAccount._meta.verbose_name = "Tài khoản ngân hàng"
FacilityBankAccount._meta.verbose_name_plural = "Tài khoản ngân hàng"


# =====================================================
# 3. QUẢN LÝ CƠ SỞ THỂ THAO
# =====================================================

@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "owner",
        "city",
        "status",
    )

    search_fields = (
        "name",
        "address",
        "city",
        "owner__username",
    )

    list_filter = ("status",)

    list_select_related = ("owner",)

    ordering = ("-created_at",)

    def has_module_permission(self, request):
        return can_manage_facilities(request.user)

    def has_view_permission(self, request, obj=None):
        user = request.user

        if is_system_admin(user):
            return True

        if is_court_owner(user):
            return obj is None or obj.owner_id == user.pk

        return False

    def has_add_permission(self, request):
        return can_manage_facilities(request.user)

    def has_change_permission(self, request, obj=None):
        user = request.user

        if is_system_admin(user):
            return True

        if is_court_owner(user):
            return obj is None or obj.owner_id == user.pk

        return False

    def has_delete_permission(self, request, obj=None):
        return is_system_admin(request.user)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if is_system_admin(request.user):
            return queryset

        if is_court_owner(request.user):
            return queryset.filter(owner=request.user)

        return queryset.none()

    def get_fields(self, request, obj=None):
        fields = [
            "name",
            "address",
            "city",
            "ward",
            "phone",
            "description",
        ]

        # Nếu model đã có trường image
        if hasattr(Facility, "image"):
            fields.append("image")

        if is_system_admin(request.user):
            fields.insert(0, "owner")
            fields.append("status")

        return fields

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs
    ):
        if db_field.name == "owner":
            from django.contrib.auth import get_user_model

            User = get_user_model()

            kwargs["queryset"] = User.objects.filter(
                role="OWNER",
                is_active=True
            )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )

    def save_model(self, request, obj, form, change):

        if is_court_owner(request.user):

            if change:
                original = Facility.objects.get(pk=obj.pk)

                if original.owner_id != request.user.pk:
                    raise PermissionDenied(
                        "Bạn không được sửa cơ sở của người khác."
                    )

                # Chủ sân không thể thay đổi trạng thái duyệt
                obj.status = original.status

            else:
                # Cơ sở mới luôn thuộc chủ sân đăng nhập
                obj.owner = request.user
                obj.status = Facility.Status.PENDING

        super().save_model(request, obj, form, change)


# =====================================================
# 4. DANH MỤC TIỆN ÍCH CHUNG
# =====================================================

@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):

    list_display = ("id", "name", "icon")

    search_fields = ("name",)

    def has_module_permission(self, request):
        return is_system_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_system_admin(request.user)

    def has_add_permission(self, request):
        return is_system_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_system_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_system_admin(request.user)


# =====================================================
# 5. QUẢN LÝ TIỆN ÍCH CỦA TỪNG CƠ SỞ
# =====================================================

@admin.register(FacilityAmenity)
class FacilityAmenityAdmin(admin.ModelAdmin):

    list_display = (
        "facility",
        "amenity",
    )

    list_filter = ("amenity",)

    search_fields = (
        "facility__name",
        "amenity__name",
    )

    list_select_related = (
        "facility",
        "amenity",
    )

    def has_module_permission(self, request):
        return can_manage_facilities(request.user)

    def has_view_permission(self, request, obj=None):
        if is_system_admin(request.user):
            return True

        if is_court_owner(request.user):
            return (
                obj is None
                or obj.facility.owner_id == request.user.pk
            )

        return False

    def has_add_permission(self, request):
        return can_manage_facilities(request.user)

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if is_system_admin(request.user):
            return queryset

        if is_court_owner(request.user):
            return queryset.filter(
                facility__owner=request.user
            )

        return queryset.none()

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs
    ):
        if db_field.name == "facility":
            if is_court_owner(request.user):
                kwargs["queryset"] = owned_facilities(
                    request.user
                )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )


# =====================================================
# 6. FORM KIỂM TRA TÀI KHOẢN NGÂN HÀNG
# =====================================================

class FacilityBankAccountForm(forms.ModelForm):

    class Meta:
        model = FacilityBankAccount
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()

        facility = cleaned_data.get("facility")
        is_active = cleaned_data.get("is_active")
        is_default = cleaned_data.get("is_default")

        if is_default and not is_active:
            raise ValidationError(
                "Tài khoản mặc định phải đang hoạt động."
            )

        if facility and is_default:

            existing_accounts = (
                FacilityBankAccount.objects.filter(
                    facility=facility,
                    is_default=True
                )
            )

            if self.instance.pk:
                existing_accounts = (
                    existing_accounts.exclude(
                        pk=self.instance.pk
                    )
                )

            if existing_accounts.exists():
                raise ValidationError(
                    "Cơ sở này đã có tài khoản ngân hàng "
                    "mặc định. Hãy bỏ chọn mặc định "
                    "ở tài khoản cũ trước."
                )

        return cleaned_data


# =====================================================
# 7. QUẢN LÝ TÀI KHOẢN NGÂN HÀNG
# =====================================================

@admin.register(FacilityBankAccount)
class FacilityBankAccountAdmin(admin.ModelAdmin):

    form = FacilityBankAccountForm

    list_display = (
        "id",
        "facility",
        "bank_code",
        "account_number",
        "account_name",
        "is_active",
        "is_default",
    )

    list_filter = (
        "bank_code",
        "is_active",
        "is_default",
    )

    search_fields = (
        "facility__name",
        "account_number",
        "account_name",
    )

    list_select_related = ("facility",)

    ordering = (
        "facility__name",
        "-is_default",
    )

    fieldsets = (
        (
            "Thông tin cơ sở",
            {
                "fields": ("facility",)
            }
        ),
        (
            "Thông tin ngân hàng",
            {
                "fields": (
                    "bank_code",
                    "account_number",
                    "account_name",
                )
            }
        ),
        (
            "Trạng thái sử dụng",
            {
                "fields": (
                    "is_active",
                    "is_default",
                )
            }
        ),
    )

    def has_module_permission(self, request):
        return can_manage_facilities(request.user)

    def has_view_permission(self, request, obj=None):
        if is_system_admin(request.user):
            return True

        if is_court_owner(request.user):
            return (
                obj is None
                or obj.facility.owner_id == request.user.pk
            )

        return False

    def has_add_permission(self, request):
        return can_manage_facilities(request.user)

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if is_system_admin(request.user):
            return queryset

        if is_court_owner(request.user):
            return queryset.filter(
                facility__owner=request.user
            )

        return queryset.none()

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs
    ):
        if db_field.name == "facility":
            if is_court_owner(request.user):
                kwargs["queryset"] = owned_facilities(
                    request.user
                )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )

    def get_readonly_fields(self, request, obj=None):
        if obj and is_court_owner(request.user):
            return ("facility",)

        return ()

    def save_model(self, request, obj, form, change):
        if is_court_owner(request.user):

            if change:
                original = (
                    FacilityBankAccount.objects
                    .select_related("facility")
                    .get(pk=obj.pk)
                )

                if original.facility.owner_id != request.user.pk:
                    raise PermissionDenied(
                        "Bạn không được sửa tài khoản "
                        "ngân hàng của cơ sở khác."
                    )

                obj.facility = original.facility

            elif obj.facility.owner_id != request.user.pk:
                raise PermissionDenied(
                    "Bạn chỉ được thêm tài khoản ngân hàng "
                    "cho cơ sở của mình."
                )

        super().save_model(request, obj, form, change)
