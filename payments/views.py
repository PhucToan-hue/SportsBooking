
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from bookings.models import Booking
from facilities.models import FacilityBankAccount
from .models import Payment, PaymentProof


@login_required
def payment_detail(request, booking_id):
    booking = get_object_or_404(
        Booking.objects.select_related(
            "court__facility"
        ),
        pk=booking_id,
        customer=request.user
    )

    bank_account = FacilityBankAccount.objects.filter(
        facility=booking.court.facility,
        is_active=True,
        is_default=True
    ).first()

    payment = Payment.objects.filter(
        booking=booking,
        payment_type=Payment.Type.DEPOSIT,
        payment_method=Payment.Method.BANK_TRANSFER
    ).order_by("-id").first()

    qr_url = None

    if bank_account:
        params = urlencode({
            "amount": str(int(booking.deposit_amount)),
            "addInfo": booking.booking_code,
            "accountName": bank_account.account_name,
        })

        qr_url = (
            f"https://img.vietqr.io/image/"
            f"{bank_account.bank_code}-"
            f"{bank_account.account_number}-compact2.png"
            f"?{params}"
        )

    return render(
        request,
        "payments/payment_detail.html",
        {
            "booking": booking,
            "bank_account": bank_account,
            "payment": payment,
            "qr_url": qr_url,
        }
    )


@login_required
@require_POST
def submit_payment(request, booking_id):
    booking = get_object_or_404(
        Booking,
        pk=booking_id,
        customer=request.user
    )

    if booking.status != Booking.Status.PENDING_DEPOSIT:
        return redirect(
            "payment_detail",
            booking_id=booking.pk
        )

    # Chưa có tài khoản nhận tiền thì không cho báo chuyển khoản
    bank_account = FacilityBankAccount.objects.filter(
        facility=booking.court.facility,
        is_active=True,
        is_default=True
    ).first()

    if not bank_account:
        return redirect(
            "payment_detail",
            booking_id=booking.pk
        )

    transfer_reference = request.POST.get(
        "transfer_reference", ""
    ).strip()[:100]

    proof_image = request.FILES.get("image")

    # Yêu cầu ít nhất một bằng chứng
    if not transfer_reference and not proof_image:
        return render(
            request,
            "payments/payment_detail.html",
            {
                "booking": booking,
                "bank_account": bank_account,
                "payment": None,
                "error": (
                    "Vui lòng nhập mã giao dịch "
                    "hoặc tải ảnh biên lai."
                ),
            }
        )

    with transaction.atomic():
        locked_booking = Booking.objects.select_for_update().get(
            pk=booking.pk
        )

        if locked_booking.status != Booking.Status.PENDING_DEPOSIT:
            return redirect(
                "payment_detail",
                booking_id=booking.pk
            )

        if (
            locked_booking.deposit_deadline
            and timezone.now() > locked_booking.deposit_deadline
        ):
            return redirect(
                "payment_detail",
                booking_id=booking.pk
            )

        payment = Payment.objects.create(
            booking=locked_booking,
            payment_type=Payment.Type.DEPOSIT,
            payment_method=Payment.Method.BANK_TRANSFER,
            amount=locked_booking.deposit_amount,
            status=Payment.Status.PENDING,
            transaction_code=transfer_reference,
        )

        PaymentProof.objects.create(
            payment=payment,
            submitted_by=request.user,
            transfer_reference=transfer_reference,
            image=proof_image,
        )

        locked_booking.status = (
            Booking.Status.PENDING_VERIFICATION
        )
        locked_booking.save(
            update_fields=["status", "updated_at"]
        )

    return redirect(
        "payment_detail",
        booking_id=booking.pk
    )
