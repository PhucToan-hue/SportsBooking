
from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from .models import Payment, PaymentProof, Refund


# ==========================================
# QUẢN LÝ THANH TOÁN
# ==========================================

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "booking",
        "get_facility",
        "get_customer",
        "payment_type",
        "payment_method",
        "amount",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "payment_type",
        "payment_method",
        "created_at",
    )

    search_fields = (
        "booking__booking_code",
        "booking__court__facility__name",
        "transaction_code",
    )

    readonly_fields = (
        "booking",
        "payment_type",
        "payment_method",
        "amount",
        "status",
        "transaction_code",
        "verified_by",
        "verified_at",
        "paid_at",
        "created_at",
    )

    actions = [
        "confirm_received_payment",
    ]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        queryset = queryset.select_related(
            "booking",
            "booking__customer",
            "booking__court",
            "booking__court__facility",
        )

        if request.user.is_superuser:
            return queryset

        return queryset.filter(
            booking__court__facility__owner=request.user
        )

    def has_view_permission(self, request, obj=None):
        if not request.user.is_staff:
            return False

        if obj is None:
            return True

        return (
            request.user.is_superuser
            or obj.booking.court.facility.owner_id
            == request.user.pk
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if not request.user.is_staff:
            return False

        if obj is None:
            return True

        return (
            request.user.is_superuser
            or obj.booking.court.facility.owner_id
            == request.user.pk
        )

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Cơ sở")
    def get_facility(self, obj):
        return obj.booking.court.facility.name

    @admin.display(description="Khách hàng")
    def get_customer(self, obj):
        return obj.booking.customer

    @admin.action(
        description="XÁC NHẬN ĐÃ NHẬN TIỀN CỌC"
    )
    def confirm_received_payment(self, request, queryset):

        confirmed = 0
        skipped = 0

        # Không tin vào danh sách ID gửi từ trình duyệt.
        # Chỉ xử lý các khoản thanh toán user được phép xem.
        allowed_ids = list(
            self.get_queryset(request)
            .filter(pk__in=queryset.values("pk"))
            .values_list("pk", flat=True)
        )

        for payment_id in allowed_ids:

            with transaction.atomic():

                payment = (
                    Payment.objects
                    .select_for_update()
                    .select_related(
                        "booking__court__facility"
                    )
                    .get(pk=payment_id)
                )

                booking = (
                    Booking.objects
                    .select_for_update()
                    .get(pk=payment.booking_id)
                )

                # Kiểm tra lại quyền chủ sân
                is_owner = (
                    payment.booking.court.facility.owner_id
                    == request.user.pk
                )

                if not request.user.is_superuser and not is_owner:
                    skipped += 1
                    continue

                # Chỉ xác nhận tiền cọc chuyển khoản
                if (
                    payment.payment_type != Payment.Type.DEPOSIT
                    or payment.payment_method
                    != Payment.Method.BANK_TRANSFER
                    or payment.status != Payment.Status.PENDING
                    or booking.status
                    != Booking.Status.PENDING_VERIFICATION
                    or payment.amount != booking.deposit_amount
                    or not payment.proofs.exists()
                ):
                    skipped += 1
                    continue

                # Tránh xác nhận trùng nhiều Payment
                if Payment.objects.filter(
                    booking=booking,
                    payment_type=Payment.Type.DEPOSIT,
                    status=Payment.Status.SUCCESS
                ).exclude(pk=payment.pk).exists():
                    skipped += 1
                    continue

                payment.status = Payment.Status.SUCCESS
                payment.verified_by = request.user
                payment.verified_at = timezone.now()
                payment.paid_at = timezone.now()

                payment.save(
                    update_fields=[
                        "status",
                        "verified_by",
                        "verified_at",
                        "paid_at",
                    ]
                )

                booking.status = Booking.Status.CONFIRMED
                booking.approved_by = request.user
                booking.approved_at = timezone.now()

                booking.save(
                    update_fields=[
                        "status",
                        "approved_by",
                        "approved_at",
                        "updated_at",
                    ]
                )

                confirmed += 1

        if confirmed:
            self.message_user(
                request,
                f"Đã xác nhận thành công {confirmed} khoản thanh toán.",
                messages.SUCCESS
            )

        if skipped:
            self.message_user(
                request,
                f"Có {skipped} khoản thanh toán không đủ điều kiện.",
                messages.WARNING
            )


# ==========================================
# QUẢN LÝ BIÊN LAI
# ==========================================

@admin.register(PaymentProof)
class PaymentProofAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "payment",
        "submitted_by",
        "transfer_reference",
        "image",
        "submitted_at",
    )

    search_fields = (
        "payment__booking__booking_code",
        "transfer_reference",
    )

    readonly_fields = (
        "payment",
        "submitted_by",
        "transfer_reference",
        "image",
        "submitted_at",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if request.user.is_superuser:
            return queryset

        return queryset.filter(
            payment__booking__court__facility__owner=request.user
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if not request.user.is_staff:
            return False

        if obj is None:
            return True

        return (
            request.user.is_superuser
            or obj.payment.booking.court.facility.owner_id
            == request.user.pk
        )

    def has_delete_permission(self, request, obj=None):
        return False


# ==========================================
# QUẢN LÝ HOÀN TIỀN
# ==========================================

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "payment",
        "amount",
        "status",
        "refunded_at",
    )

    readonly_fields = (
        "payment",
        "amount",
        "status",
        "reason",
        "refunded_at",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)

        if request.user.is_superuser:
            return queryset

        return queryset.filter(
            payment__booking__court__facility__owner=request.user
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if not request.user.is_staff:
            return False

        if obj is None:
            return True

        return (
            request.user.is_superuser
            or obj.payment.booking.court.facility.owner_id
            == request.user.pk
        )

    def has_delete_permission(self, request, obj=None):
        return False
