
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.views import redirect_to_login
from django.db import transaction
from django.db.models import Q, Prefetch
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone

from .models import Facility
from courts.models import Court, CourtPrice, CourtBlock
from bookings.models import Booking


OCCUPIED_STATUSES = [
    Booking.Status.PENDING_DEPOSIT,
    Booking.Status.PENDING_VERIFICATION,
    Booking.Status.PENDING_APPROVAL,
    Booking.Status.CONFIRMED,
    Booking.Status.COMPLETED,
]


def home(request):
    keyword = request.GET.get("q", "").strip()
    sport = request.GET.get("sport", "").strip().lower()

    facilities = Facility.objects.filter(
        status=Facility.Status.APPROVED
    )

    if keyword:
        facilities = facilities.filter(
            Q(name__icontains=keyword)
            | Q(address__icontains=keyword)
            | Q(city__icontains=keyword)
        )

    if sport:
        facilities = facilities.filter(
            courts__sport_type__slug=sport,
            courts__status=Court.Status.ACTIVE
        )

    facilities = facilities.distinct().order_by("-id")

    return render(
        request,
        "facilities/home.html",
        {
            "facilities": facilities,
            "keyword": keyword,
            "sport": sport,
        }
    )


def facility_detail(request, pk):
    facility = get_object_or_404(
        Facility,
        pk=pk,
        status=Facility.Status.APPROVED
    )

    courts = (
        Court.objects.filter(
            facility=facility,
            status=Court.Status.ACTIVE
        )
        .select_related("sport_type")
        .prefetch_related(
            "images",
            "operating_hours",
            Prefetch(
                "prices",
                queryset=CourtPrice.objects.filter(
                    is_active=True
                ).order_by("price_per_hour")
            )
        )
    )

    court_data = []

    for court in courts:
        images = list(court.images.all())
        prices = list(court.prices.all())

        primary_image = next(
            (image for image in images if image.is_primary),
            images[0] if images else None
        )

        court_data.append({
            "court": court,
            "primary_image": primary_image,
            "min_price": (
                prices[0].price_per_hour if prices else None
            ),
            "prices": prices,
            "operating_hours": sorted(
                court.operating_hours.all(),
                key=lambda hour: hour.day_of_week
            ),
        })

    return render(
        request,
        "facilities/detail.html",
        {
            "facility": facility,
            "court_data": court_data,
        }
    )


def get_slot_price(court, selected_date, start_clock, end_clock):
    """
    Tìm giá theo CourtPrice.
    Nếu có nhiều bảng giá chồng lấn thì không cho đặt,
    tránh tính sai tiền.
    """
    matches = CourtPrice.objects.filter(
        court=court,
        day_of_week=selected_date.weekday(),
        is_active=True,
        effective_from__lte=selected_date,
        start_time__lte=start_clock,
        end_time__gte=end_clock
    ).filter(
        Q(effective_to__isnull=True)
        | Q(effective_to__gte=selected_date)
    )

    prices = list(matches[:2])

    if len(prices) != 1:
        return None

    return prices[0].price_per_hour * Decimal("0.5")


def calculate_booking(court, selected_date, start_clock, end_clock):
    """
    Kiểm tra và tính lại tiền hoàn toàn ở Django.
    Trả về (dữ liệu, lỗi).
    """

    if start_clock.second or start_clock.microsecond:
        return None, "Giờ bắt đầu không hợp lệ."

    if end_clock.second or end_clock.microsecond:
        return None, "Giờ kết thúc không hợp lệ."

    start_minutes = start_clock.hour * 60 + start_clock.minute
    end_minutes = end_clock.hour * 60 + end_clock.minute

    if start_minutes < 330 or end_minutes > 1380:
        return None, "Khung giờ nằm ngoài lịch đặt sân."

    if (
        start_minutes % 30 != 0
        or end_minutes % 30 != 0
        or end_minutes <= start_minutes
    ):
        return None, "Vui lòng chọn các ô 30 phút liên tiếp."

    tz = timezone.get_current_timezone()

    start_dt = timezone.make_aware(
        datetime.combine(selected_date, start_clock),
        tz
    )

    end_dt = timezone.make_aware(
        datetime.combine(selected_date, end_clock),
        tz
    )

    if start_dt <= timezone.now():
        return None, "Không thể đặt khung giờ đã qua."

    has_booking = Booking.objects.filter(
        court=court,
        status__in=OCCUPIED_STATUSES,
        start_time__lt=end_dt,
        end_time__gt=start_dt
    ).exists()

    if has_booking:
        return None, "Khung giờ này đã có khách đặt."

    has_block = CourtBlock.objects.filter(
        court=court,
        start_time__lt=end_dt,
        end_time__gt=start_dt
    ).exists()

    if has_block:
        return None, "Khung giờ này đã bị khóa."

    total = Decimal("0.00")

    for minute in range(start_minutes, end_minutes, 30):
        slot_start = time(minute // 60, minute % 60)

        next_minute = minute + 30
        slot_end = time(
            next_minute // 60,
            next_minute % 60
        )

        price = get_slot_price(
            court,
            selected_date,
            slot_start,
            slot_end
        )

        if price is None:
            return None, (
                "Một hoặc nhiều khung giờ chưa có "
                "bảng giá hợp lệ hoặc bị trùng bảng giá."
            )

        total += price

    total = total.quantize(Decimal("0.01"))

    return {
        "court": court,
        "selected_date": selected_date,
        "start_clock": start_clock,
        "end_clock": end_clock,
        "start_dt": start_dt,
        "end_dt": end_dt,
        "duration_minutes": end_minutes - start_minutes,
        "total": total,
        "deposit": total,
        "remaining": Decimal("0.00"),
    }, None


def facility_booking(request, pk):
    facility = get_object_or_404(
        Facility,
        pk=pk,
        status=Facility.Status.APPROVED
    )

    today = timezone.localdate()

    # =====================================
    # XỬ LÝ XÁC NHẬN VÀ TẠO BOOKING
    # =====================================
    if request.method == "POST":

        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path()
            )

        action = request.POST.get("action", "preview")

        if action not in ("preview", "create"):
            return render(
                request,
                "facilities/confirm_booking.html",
                {
                    "facility": facility,
                    "error": "Thao tác không hợp lệ.",
                }
            )

        try:
            selected_date = date.fromisoformat(
                request.POST.get("date", "")
            )

            start_clock = time.fromisoformat(
                request.POST.get("start", "")
            )

            end_clock = time.fromisoformat(
                request.POST.get("end", "")
            )

            court_id = int(
                request.POST.get("court_id", "")
            )

        except (ValueError, TypeError):
            return render(
                request,
                "facilities/confirm_booking.html",
                {
                    "facility": facility,
                    "error": "Thông tin ngày, sân hoặc giờ không hợp lệ.",
                }
            )

        court = get_object_or_404(
            Court,
            pk=court_id,
            facility=facility,
            status=Court.Status.ACTIVE
        )

        # Chỉ xem trước thông tin
        if action == "preview":
            booking_data, error = calculate_booking(
                court,
                selected_date,
                start_clock,
                end_clock
            )

            return render(
                request,
                "facilities/confirm_booking.html",
                {
                    "facility": facility,
                    "booking_data": booking_data,
                    "error": error,
                    "created_booking": None,
                }
            )

        # Tạo Booking thật trong giao dịch.
        # Khóa hàng Court để tuần tự hóa
        # các yêu cầu đặt cùng một sân.
        with transaction.atomic():

            locked_court = get_object_or_404(
                Court.objects.select_for_update(),
                pk=court_id,
                facility=facility,
                status=Court.Status.ACTIVE
            )

            booking_data, error = calculate_booking(
                locked_court,
                selected_date,
                start_clock,
                end_clock
            )

            if error:
                return render(
                    request,
                    "facilities/confirm_booking.html",
                    {
                        "facility": facility,
                        "error": error,
                    }
                )

            booking_code = (
                "SB"
                + timezone.now().strftime("%y%m%d")
                + uuid4().hex[:12].upper()
            )

            created_booking = Booking.objects.create(
                booking_code=booking_code,
                customer=request.user,
                court=locked_court,
                start_time=booking_data["start_dt"],
                end_time=booking_data["end_dt"],
                total_amount=booking_data["total"],
                deposit_amount=booking_data["deposit"],
                remaining_amount=booking_data["remaining"],
                status=Booking.Status.PENDING_DEPOSIT,
                deposit_deadline=(
                    timezone.now() + timedelta(minutes=15)
                ),
            )

        return render(
            request,
            "facilities/confirm_booking.html",
            {
                "facility": facility,
                "booking_data": booking_data,
                "created_booking": created_booking,
            }
        )

    # =====================================
    # HIỂN THỊ BẢNG LỊCH (GET)
    # =====================================

    try:
        selected_date = date.fromisoformat(
            request.GET.get("date", "")
        )
    except (ValueError, TypeError):
        selected_date = today

    if selected_date < today:
        selected_date = today

    courts = (
        Court.objects.filter(
            facility=facility,
            status=Court.Status.ACTIVE
        )
        .select_related("sport_type")
        .order_by("id")
    )

    minutes = list(range(330, 1380, 30))

    def to_time(value):
        return time(value // 60, value % 60)

    time_labels = [
        to_time(value).strftime("%H:%M")
        for value in minutes
    ]

    tz = timezone.get_current_timezone()

    day_start = timezone.make_aware(
        datetime.combine(selected_date, time.min),
        tz
    )

    day_end = timezone.make_aware(
        datetime.combine(
            selected_date + timedelta(days=1),
            time.min
        ),
        tz
    )

    now = timezone.now()
    court_rows = []

    for court in courts:

        bookings = list(
            Booking.objects.filter(
                court=court,
                status__in=OCCUPIED_STATUSES,
                start_time__lt=day_end,
                end_time__gt=day_start
            )
        )

        blocks = list(
            CourtBlock.objects.filter(
                court=court,
                start_time__lt=day_end,
                end_time__gt=day_start
            )
        )

        slots = []

        for minute in minutes:

            start_clock = to_time(minute)
            end_clock = to_time(minute + 30)

            slot_start = timezone.make_aware(
                datetime.combine(
                    selected_date,
                    start_clock
                ),
                tz
            )

            slot_end = slot_start + timedelta(minutes=30)

            is_booked = any(
                booking.start_time < slot_end
                and booking.end_time > slot_start
                for booking in bookings
            )

            is_blocked = any(
                block.start_time < slot_end
                and block.end_time > slot_start
                for block in blocks
            )

            slot_price = get_slot_price(
                court,
                selected_date,
                start_clock,
                end_clock
            )

            if is_booked:
                status = "booked"
            elif is_blocked or slot_start <= now:
                status = "locked"
            elif slot_price is None:
                status = "locked"
            else:
                status = "free"

            slots.append({
                "start": start_clock.strftime("%H:%M"),
                "end": end_clock.strftime("%H:%M"),
                "status": status,
                "price": (
                    format(slot_price, "f")
                    if slot_price is not None
                    else ""
                ),
                "hourly_price": (
                    format(slot_price * Decimal("2"), "f")
                    if slot_price is not None
                    else ""
                ),
            })

        court_rows.append({
            "court": court,
            "slots": slots,
        })

    return render(
        request,
        "facilities/booking.html",
        {
            "facility": facility,
            "selected_date": selected_date,
            "today": today,
            "time_labels": time_labels,
            "court_rows": court_rows,
            "deposit_percent": 100,
        }
    )
