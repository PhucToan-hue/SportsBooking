
from django.contrib import admin
from django.core.exceptions import PermissionDenied

from facilities.models import Facility

from .models import (
    SportType,
    Court,
    CourtImage,
    OperatingHour,
    CourtPrice,
    CourtBlock,
)


# =====================================================
# 1. PHÂN QUYỀN ADMIN
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


def can_manage_courts(user):
    return is_system_admin(user) or is_court_owner(user)


def allowed_courts(user):
    if is_system_admin(user):
        return Court.objects.all()

    if is_court_owner(user):
        return Court.objects.filter(
            facility__owner=user
        )

    return Court.objects.none()


# =====================================================
# 2. VIỆT HÓA TÊN MODEL
# =====================================================

SportType._meta.verbose_name = "Loại hình thể thao"
SportType._meta.verbose_name_plural = "Loại hình thể thao"

Court._meta.verbose_name = "Sân thể thao"
Court._meta.verbose_name_plural = "Danh sách sân thể thao"

CourtImage._meta.verbose_name = "Hình ảnh sân"
CourtImage._meta.verbose_name_plural = "Hình ảnh sân"

OperatingHour._meta.verbose_name = "Giờ hoạt động"
OperatingHour._meta.verbose_name_plural = "Giờ hoạt động"

CourtPrice._meta.verbose_name = "Bảng giá sân"
CourtPrice._meta.verbose_name_plural = "Bảng giá sân"

CourtBlock._meta.verbose_name = "Lịch khóa sân"
CourtBlock._meta.verbose_name_plural = "Lịch khóa sân"


# =====================================================
# 3. ADMIN CHUNG CHO CÁC MODEL CÓ FOREIGNKEY COURT
# =====================================================

class OwnerCourtRelatedAdmin(admin.ModelAdmin):

    def has_module_permission(self, request):
        return can_manage_courts(request.user)

    def has_view_permission(self, request, obj=None):
        user = request.user

        if is_system_admin(user):
            return True

        if is_court_owner(user):
            return (
                obj is None
                or obj.court.facility.owner_id == user.pk
            )

        return False

    def has_add_permission(self, request):
        return can_manage_courts(request.user)

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
                court__facility__owner=request.user
            )

        return queryset.none()

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs
    ):
        if db_field.name == "court":
            kwargs["queryset"] = allowed_courts(
                request.user
            )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs
        )

    def get_readonly_fields(self, request, obj=None):
        if obj and is_court_owner(request.user):
            return ("court",)

        return ()

    def save_model(self, request, obj, form, change):

        if is_court_owner(request.user):

            if change:
                original = (
                    self.model.objects
                    .select_related("court__facility")
                    .get(pk=obj.pk)
                )

                if (
                    original.court.facility.owner_id
                    != request.user.pk
                ):
                    raise PermissionDenied(
                        "Bạn không có quyền sửa "
                        "dữ liệu của sân khác."
                    )

                obj.court = original.court

            elif not allowed_courts(
                request.user
            ).filter(pk=obj.court_id).exists():
                raise PermissionDenied(
                    "Bạn chỉ được thêm dữ liệu "
                    "cho sân thuộc cơ sở của mình."
                )

        super().save_model(
            request,
            obj,
            form,
            change
        )


# =====================================================
# 4. LOẠI HÌNH THỂ THAO
# =====================================================

@admin.register(SportType)
class SportTypeAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "slug",
    )

    search_fields = (
        "name",
        "slug",
    )

    def has_module_permission(self, request):
        return can_manage_courts(request.user)

    def has_view_permission(self, request, obj=None):
        return can_manage_courts(request.user)

    def has_add_permission(self, request):
        return is_system_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_system_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_system_admin(request.user)


# =====================================================
# 5. QUẢN LÝ DANH SÁCH SÂN
# =====================================================

@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "facility",
        "sport_type",
        "status",
    )

    list_filter = (
        "sport_type",
        "status",
    )

    search_fields = (
        "name",
        "facility__name",
    )

    list_select_related = (
        "facility",
        "sport_type",
    )

    ordering = ("-created_at",)

    def has_module_permission(self, request):
        return can_manage_courts(request.user)

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
        return can_manage_courts(request.user)

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return is_system_admin(request.user)

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

            queryset = Facility.objects.all()

            if is_court_owner(request.user):
                queryset = queryset.filter(
                    owner=request.user
                )

            kwargs["queryset"] = queryset

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
                original = Court.objects.get(pk=obj.pk)

                if original.facility.owner_id != request.user.pk:
                    raise PermissionDenied(
                        "Bạn không được sửa sân "
                        "của cơ sở khác."
                    )

                obj.facility = original.facility

            elif obj.facility.owner_id != request.user.pk:
                raise PermissionDenied(
                    "Bạn chỉ được thêm sân vào "
                    "cơ sở của mình."
                )

        super().save_model(
            request,
            obj,
            form,
            change
        )


# =====================================================
# 6. QUẢN LÝ HÌNH ẢNH SÂN
# =====================================================

@admin.register(CourtImage)
class CourtImageAdmin(OwnerCourtRelatedAdmin):

    list_display = (
        "id",
        "court",
        "is_primary",
    )

    list_filter = ("is_primary",)

    search_fields = (
        "court__name",
        "court__facility__name",
    )


# =====================================================
# 7. QUẢN LÝ GIỜ HOẠT ĐỘNG
# =====================================================

@admin.register(OperatingHour)
class OperatingHourAdmin(OwnerCourtRelatedAdmin):

    list_display = (
        "id",
        "court",
        "day_of_week",
        "open_time",
        "close_time",
        "is_closed",
    )

    list_filter = (
        "day_of_week",
        "is_closed",
    )

    search_fields = (
        "court__name",
        "court__facility__name",
    )


# =====================================================
# 8. QUẢN LÝ BẢNG GIÁ SÂN
# =====================================================

@admin.register(CourtPrice)
class CourtPriceAdmin(OwnerCourtRelatedAdmin):

    list_display = (
        "id",
        "court",
        "day_of_week",
        "start_time",
        "end_time",
        "price_per_hour",
        "effective_from",
        "effective_to",
        "is_active",
    )

    list_filter = (
        "day_of_week",
        "is_active",
    )

    search_fields = (
        "court__name",
        "court__facility__name",
    )


# =====================================================
# 9. QUẢN LÝ LỊCH KHÓA SÂN
# =====================================================

@admin.register(CourtBlock)
class CourtBlockAdmin(OwnerCourtRelatedAdmin):

    list_display = (
        "id",
        "court",
        "start_time",
        "end_time",
        "reason",
    )

    search_fields = (
        "court__name",
        "court__facility__name",
        "reason",
    )
