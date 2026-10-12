
from django.contrib import admin
from django.core.exceptions import ValidationError
from django import forms

from .models import (
    Facility,
    Amenity,
    FacilityAmenity,
    FacilityBankAccount,
)


# ==========================================
# VIỆT HÓA TÊN CÁC BẢNG
# ==========================================

Facility._meta.verbose_name = "Cơ sở thể thao"
Facility._meta.verbose_name_plural = "Danh sách cơ sở thể thao"

Amenity._meta.verbose_name = "Tiện ích"
Amenity._meta.verbose_name_plural = "Danh sách tiện ích"

FacilityAmenity._meta.verbose_name = "Tiện ích cơ sở"
FacilityAmenity._meta.verbose_name_plural = "Tiện ích của cơ sở"

FacilityBankAccount._meta.verbose_name = "Tài khoản ngân hàng"
FacilityBankAccount._meta.verbose_name_plural = "Tài khoản ngân hàng"


# ==========================================
# QUẢN LÝ CƠ SỞ THỂ THAO
# ==========================================

@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "owner",
        "status",
    )

    search_fields = (
        "name",
        "address",
        "city",
    )

    list_filter = (
        "status",
    )


# ==========================================
# QUẢN LÝ TIỆN ÍCH
# ==========================================

@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    search_fields = ("name",)


@admin.register(FacilityAmenity)
class FacilityAmenityAdmin(admin.ModelAdmin):
    list_display = (
        "facility",
        "amenity",
    )

    list_filter = ("facility",)


# ==========================================
# KIỂM TRA TÀI KHOẢN NGÂN HÀNG
# ==========================================

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
                existing_accounts = existing_accounts.exclude(
                    pk=self.instance.pk
                )

            if existing_accounts.exists():
                raise ValidationError(
                    "Cơ sở này đã có tài khoản ngân hàng mặc định. "
                    "Hãy bỏ chọn mặc định ở tài khoản cũ trước."
                )

        return cleaned_data


# ==========================================
# QUẢN LÝ TÀI KHOẢN NGÂN HÀNG
# ==========================================

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

    list_editable = (
        "is_active",
    )

    list_select_related = (
        "facility",
    )

    ordering = (
        "facility__name",
        "-is_default",
    )

    fieldsets = (
        (
            "Thông tin cơ sở",
            {
                "fields": (
                    "facility",
                )
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
