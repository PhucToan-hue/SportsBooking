
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from bookings.models import Booking
from courts.models import Court
from payments.models import Payment, Refund

from .views import owner_required


PENDING_STATUSES = (
    Booking.Status.PENDING_DEPOSIT,
    Booking.Status.PENDING_VERIFICATION,
    Booking.Status.PENDING_APPROVAL,
)

OCCUPIED_STATUSES = (
    Booking.Status.PENDING_DEPOSIT,
    Booking.Status.PENDING_VERIFICATION,
    Booking.Status.PENDING_APPROVAL,
    Booking.Status.CONFIRMED,
)

STATUS_FILTERS = [
    ("pending", "Chờ xử lý"),
    (Booking.Status.PENDING_DEPOSIT, "Chờ đặt cọc"),
    (Booking.Status.PENDING_VERIFICATION, "Chờ xác minh"),
    (Booking.Status.PENDING_APPROVAL, "Chờ duyệt"),
    (Booking.Status.CONFIRMED, "Đã xác nhận"),
    (Booking.Status.COMPLETED, "Hoàn thành"),
    (Booking.Status.CANCELLED, "Đã hủy"),
    (Booking.Status.REJECTED, "Từ chối"),
    (Booking.Status.EXPIRED, "Hết hạn"),
    ("all", "Tất cả"),
]


def online_bookings(request):
    # Đơn tại quầy hiện được tạo với mã bắt đầu QUAY.
    return Booking.objects.filter(
        court__facility__owner=request.user
    ).exclude(
        booking_code__startswith="QUAY"
    )


def verified_amount(payments):
    return sum(
        (
            payment.amount
            for payment in payments
            if (
                payment.payment_type == Payment.Type.DEPOSIT
                and payment.status == Payment.Status.SUCCESS
            )
        ),
        Decimal("0.00"),
    )


def payment_is_complete(booking, payments):
    return (
        booking.total_amount > 0
        and verified_amount(payments) >= booking.total_amount
    )


@owner_required
def booking_approvals_view(request):
    selected_status = request.GET.get("status", "pending")

    valid_filters = {item[0] for item in STATUS_FILTERS}

    if selected_status not in valid_filters:
        selected_status = "pending"

    base_queryset = online_bookings(request)

    # Đếm trên toàn bộ đơn trước khi áp dụng bộ lọc.
    counts = dict(
        base_queryset.values("status")
        .annotate(total=Count("id"))
        .values_list("status", "total")
    )

    total_count = sum(counts.values())
    pending_count = sum(
        counts.get(status, 0)
        for status in PENDING_STATUSES
    )

    filters = []

    for value, label in STATUS_FILTERS:
        if value == "all":
            count = total_count
        elif value == "pending":
            count = pending_count
        else:
            count = counts.get(value, 0)

        filters.append({
            "value": value,
            "label": label,
            "count": count,
        })

    if selected_status == "pending":
        base_queryset = base_queryset.filter(
            status__in=PENDING_STATUSES
        )
    elif selected_status != "all":
        base_queryset = base_queryset.filter(
            status=selected_status
        )

    payment_queryset = Payment.objects.order_by(
        "-created_at"
    ).prefetch_related("proofs")

    bookings = list(
        base_queryset.select_related(
            "customer",
            "court",
            "court__facility",
        ).prefetch_related(
            Prefetch(
                "payments",
                queryset=payment_queryset,
                to_attr="approval_payments",
            )
        ).order_by("-created_at")[:100]
    )

    for booking in bookings:
        payments = booking.approval_payments

        booking.verified_deposit_total = verified_amount(
            payments
        )
        booking.payment_complete = payment_is_complete(
            booking, payments
        )

        booking.can_approve = (
            booking.status in PENDING_STATUSES
        )

        booking.can_reject = (
            booking.status in PENDING_STATUSES
        )

        booking.has_pending_payment = any(
            payment.payment_type == Payment.Type.DEPOSIT
            and payment.payment_method == Payment.Method.BANK_TRANSFER
            and payment.status == Payment.Status.PENDING
            for payment in payments
        )

        booking.can_verify = (
            booking.status in PENDING_STATUSES
            or booking.status == Booking.Status.CONFIRMED
        )

    return render(
        request,
        "owner_dashboard/booking_approvals.html",
        {
            "bookings": bookings,
            "filters": filters,
            "selected_status": selected_status,
            "total_count": total_count,
            "pending_count": pending_count,
        },
    )


@owner_required
@require_POST
def booking_approval_action(request, booking_id):
    action = request.POST.get("action", "").strip()
    reason = request.POST.get("reason", "").strip()

    if action not in ("approve", "reject", "verify"):
        messages.error(request, "Thao tác không hợp lệ.")
        return redirect("owner_dashboard:booking_approvals")

    if action == "reject" and not reason:
        messages.error(
            request,
            "Vui lòng nhập lý do từ chối đơn."
        )
        return redirect("owner_dashboard:booking_approvals")

    if len(reason) > 2000:
        messages.error(
            request,
            "Lý do từ chối quá dài."
        )
        return redirect("owner_dashboard:booking_approvals")

    with transaction.atomic():
        # Lấy ID sân thuộc chủ sân hiện tại.
        booking_reference = get_object_or_404(
            online_bookings(request),
            pk=booking_id,
        )

        # Khóa sân trước khi khóa đơn để hạn chế
        # xung đột với quy trình đặt sân tại quầy.
        court = get_object_or_404(
            Court.objects.select_for_update(),
            pk=booking_reference.court_id,
            facility__owner=request.user,
        )

        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            pk=booking_id,
            court=court,
        )

        payments = list(
            Payment.objects.select_for_update()
            .filter(booking=booking)
            .order_by("id")
        )

        if action == "approve":
            if booking.status not in PENDING_STATUSES:
                messages.error(
                    request,
                    "Đơn này không còn chờ duyệt."
                )
                return redirect(
                    "owner_dashboard:booking_approvals"
                )

            if court.status != Court.Status.ACTIVE:
                messages.error(
                    request,
                    "Sân hiện không hoạt động."
                )
                return redirect(
                    "owner_dashboard:booking_approvals"
                )

            if booking.start_time <= timezone.now():
                messages.error(
                    request,
                    "Không thể duyệt đơn có giờ bắt đầu đã qua."
                )
                return redirect(
                    "owner_dashboard:booking_approvals"
                )

            # Kiểm tra trùng giờ với các đơn khác.
            conflict = Booking.objects.filter(
                court=court,
                status__in=OCCUPIED_STATUSES,
                start_time__lt=booking.end_time,
                end_time__gt=booking.start_time,
            ).exclude(
                pk=booking.pk
            ).exists()

            if conflict:
                messages.error(
                    request,
                    "Khung giờ này đang bị đơn khác chiếm. "
                    "Không thể duyệt."
                )
                return redirect(
                    "owner_dashboard:booking_approvals"
                )

            booking.status = Booking.Status.CONFIRMED
            booking.approved_by = request.user
            booking.approved_at = timezone.now()

            booking.save(update_fields=[
                "status",
                "approved_by",
                "approved_at",
                "updated_at",
            ])

            # Phương án B: không sửa trạng thái Payment.
            # Đã duyệt không đồng nghĩa đã nhận tiền.
            if payment_is_complete(booking, payments):
                messages.success(
                    request,
                    "Đã duyệt đơn "
                    + booking.booking_code
                    + ". Tiền cọc đã được xác minh."
                )
            else:
                messages.warning(
                    request,
                    "Đã duyệt đơn "
                    + booking.booking_code
                    + ", nhưng chưa xác minh đủ tiền cọc. "
                    "Cần tiếp tục theo dõi thanh toán."
                )

        elif action == "verify":
            if booking.status not in (
                *PENDING_STATUSES,
                Booking.Status.CONFIRMED,
            ):
                messages.error(
                    request,
                    "Không thể xác minh thanh toán "
                    "ở trạng thái đơn hiện tại."
                )
                return redirect(
                    "owner_dashboard:booking_approvals"
                )

            payment_id = request.POST.get(
                "payment_id", ""
            )

            if not payment_id.isdigit():
                messages.error(
                    request,
                    "Giao dịch không hợp lệ."
                )
                return redirect(
                    "owner_dashboard:booking_approvals"
                )

            payment = next(
                (
                    item for item in payments
                    if item.pk == int(payment_id)
                ),
                None,
            )

            if (
                payment is None
                or payment.payment_type != Payment.Type.DEPOSIT
                or payment.payment_method != Payment.Method.BANK_TRANSFER
                or payment.status != Payment.Status.PENDING
            ):
                messages.error(
                    request,
                    "Giao dịch không tồn tại "
                    "hoặc đã được xử lý."
                )
                return redirect(
                    "owner_dashboard:booking_approvals"
                )

            if (
                booking.total_amount <= 0
                or booking.deposit_amount != booking.total_amount
                or booking.remaining_amount != 0
            ):
                messages.error(
                    request,
                    "Thông tin đặt cọc 100% "
                    "của đơn không hợp lệ."
                )
                return redirect(
                    "owner_dashboard:booking_approvals"
                )

            already_paid = verified_amount(payments)

            if (
                already_paid + payment.amount
                > booking.total_amount
            ):
                messages.error(
                    request,
                    "Số tiền xác minh vượt tổng tiền đơn."
                )
                return redirect(
                    "owner_dashboard:booking_approvals"
                )

            now = timezone.now()

            payment.status = Payment.Status.SUCCESS
            payment.verified_by = request.user
            payment.verified_at = now
            payment.paid_at = now

            payment.save(update_fields=[
                "status",
                "verified_by",
                "verified_at",
                "paid_at",
            ])

            new_paid = already_paid + payment.amount

            if (
                booking.status
                in (
                    Booking.Status.PENDING_VERIFICATION,
                    Booking.Status.PENDING_DEPOSIT,
                )
                and new_paid >= booking.total_amount
            ):
                booking.status = Booking.Status.PENDING_APPROVAL
                booking.save(update_fields=[
                    "status",
                    "updated_at",
                ])

            messages.success(
                request,
                "Đã xác minh giao dịch thành công."
            )

        elif action == "reject":
            if booking.status not in PENDING_STATUSES:
                messages.error(
                    request,
                    "Chỉ có thể từ chối đơn đang chờ xử lý."
                )
                return redirect(
                    "owner_dashboard:booking_approvals"
                )

            # Không tự chuyển khoản hoàn tiền.
            # Chỉ tạo bản ghi yêu cầu hoàn tiền.
            for payment in payments:
                if (
                    payment.payment_type == Payment.Type.DEPOSIT
                    and payment.status == Payment.Status.SUCCESS
                ):
                    Refund.objects.get_or_create(
                        payment=payment,
                        defaults={
                            "amount": payment.amount,
                            "status": Refund.Status.PENDING,
                            "reason": (
                                "Từ chối đơn "
                                + booking.booking_code
                                + ": "
                                + reason
                            ),
                        },
                    )

            booking.status = Booking.Status.REJECTED
            booking.cancel_reason = reason

            booking.save(update_fields=[
                "status",
                "cancel_reason",
                "updated_at",
            ])

            messages.success(
                request,
                "Đã từ chối đơn "
                + booking.booking_code
                + ". Kiểm tra hoàn tiền nếu khách đã cọc."
            )

    return redirect("owner_dashboard:booking_approvals")
