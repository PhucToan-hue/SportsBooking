
from datetime import date, time
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone

from bookings.models import Booking
from courts.models import Court
from facilities.models import Facility
from facilities.views import calculate_booking

from .views import owner_required


@owner_required
def owner_booking_confirm(request):
    if request.method != "POST":
        return redirect("owner_dashboard:schedule")

    action = request.POST.get("action", "preview")

    if action not in ("preview", "create"):
        messages.error(request, "Thao tác không hợp lệ.")
        return redirect("owner_dashboard:schedule")

    try:
        facility_id = int(request.POST.get("facility_id", ""))
        court_id = int(request.POST.get("court_id", ""))
        selected_date = date.fromisoformat(
            request.POST.get("date", "")
        )
        start_clock = time.fromisoformat(
            request.POST.get("start", "")
        )
        end_clock = time.fromisoformat(
            request.POST.get("end", "")
        )
    except (ValueError, TypeError):
        messages.error(
            request,
            "Thông tin sân hoặc khung giờ không hợp lệ."
        )
        return redirect("owner_dashboard:schedule")

    facility = get_object_or_404(
        Facility,
        pk=facility_id,
        owner=request.user,
    )

    court = get_object_or_404(
        Court,
        pk=court_id,
        facility=facility,
        status=Court.Status.ACTIVE,
    )

    customer_name = request.POST.get(
        "customer_name", ""
    ).strip()

    customer_phone = request.POST.get(
        "customer_phone", ""
    ).strip()

    note = request.POST.get("note", "").strip()
    paid_deposit = request.POST.get("paid_deposit") == "on"

    booking_data, error = calculate_booking(
        court,
        selected_date,
        start_clock,
        end_clock,
    )

    if action == "create" and not error:
        if not customer_name:
            error = "Vui lòng nhập tên khách hàng."

        elif not (
            customer_phone.isdigit()
            and 9 <= len(customer_phone) <= 11
        ):
            error = "Số điện thoại không hợp lệ."

        else:
            with transaction.atomic():
                locked_court = get_object_or_404(
                    Court.objects.select_for_update(),
                    pk=court.pk,
                    facility__owner=request.user,
                    status=Court.Status.ACTIVE,
                )

                booking_data, error = calculate_booking(
                    locked_court,
                    selected_date,
                    start_clock,
                    end_clock,
                )

                if not error:
                    User = get_user_model()

                    customer = User.objects.filter(
                        phone=customer_phone
                    ).first()

                    if customer:
                        if customer.role != User.Role.CUSTOMER:
                            error = (
                                "Số điện thoại đã thuộc tài khoản "
                                "không phải khách hàng."
                            )
                    else:
                        uid = uuid4().hex

                        customer = User(
                            username="quay_" + uid[:20],
                            email=uid + "@matchup.invalid",
                            full_name=customer_name,
                            phone=customer_phone,
                            role=User.Role.CUSTOMER,
                        )
                        customer.set_unusable_password()
                        customer.save()

                    if not error:
                        total = booking_data["total"]

                        deposit = (
                            total if paid_deposit else total * 0
                        )

                        booking = Booking.objects.create(
                            booking_code=(
                                "QUAY"
                                + timezone.now().strftime("%y%m%d")
                                + uuid4().hex[:12].upper()
                            ),
                            customer=customer,
                            court=locked_court,
                            start_time=booking_data["start_dt"],
                            end_time=booking_data["end_dt"],
                            total_amount=total,
                            deposit_amount=deposit,
                            remaining_amount=total - deposit,
                            status=Booking.Status.CONFIRMED,
                            approved_by=request.user,
                            approved_at=timezone.now(),
                        )

            if not error:
                messages.success(
                    request,
                    "Đặt sân tại quầy thành công! "
                    "Mã đơn: " + booking.booking_code
                )
                return redirect(
                    "owner_dashboard:booking_list"
                )

    context = {
        "facility": facility,
        "court": court,
        "booking_data": booking_data,
        "selected_date": selected_date,
        "start_clock": start_clock,
        "end_clock": end_clock,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "note": note,
        "paid_deposit": paid_deposit,
        "error": error,
        "duration_hours": (
            booking_data["duration_minutes"] / 60
            if booking_data else 0
        ),
    }

    return render(
        request,
        "owner_dashboard/booking_confirm.html",
        context,
    )
