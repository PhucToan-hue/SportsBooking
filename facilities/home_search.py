
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from bookings.models import Booking
from courts.models import (
    Court,
    CourtBlock,
    OperatingHour,
    SportType,
)
from facilities.models import Facility


DURATIONS = [
    (30, "30 phút"),
    (60, "1 giờ"),
    (90, "1 giờ 30 phút"),
    (120, "2 giờ"),
    (150, "2 giờ 30 phút"),
    (180, "3 giờ"),
]


def home_search(request):
    from .views import calculate_booking, OCCUPIED_STATUSES

    today = timezone.localdate()

    keyword = request.GET.get("q", "").strip()
    sport = request.GET.get("sport", "").strip().lower()
    date_value = request.GET.get("date", "").strip()
    time_value = request.GET.get("time", "").strip()
    duration_value = request.GET.get("duration", "60").strip()

    has_search = request.GET.get("search") == "1"

    results = []
    error = None

    # ==================================================
    # 1. DANH SÁCH MÔN THỂ THAO
    # ==================================================

    sports = (
        SportType.objects.filter(
            court__status=Court.Status.ACTIVE,
            court__facility__status=Facility.Status.APPROVED,
        )
        .distinct()
        .order_by("name")
    )

    # Giờ bắt đầu: 05:30 - 22:30
    time_options = [
        time(minute // 60, minute % 60).strftime("%H:%M")
        for minute in range(330, 1351, 30)
    ]

    # ==================================================
    # 2. DANH SÁCH CƠ SỞ
    # ==================================================

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
            courts__status=Court.Status.ACTIVE,
        )

    facilities = facilities.distinct().order_by("-id")

    # ==================================================
    # 3. TÌM CƠ SỞ CÓ SÂN TRỐNG
    # ==================================================

    if has_search:
        try:
            if not sport or not sports.filter(slug=sport).exists():
                raise ValueError(
                    "Vui lòng chọn môn thể thao hợp lệ."
                )

            selected_date = date.fromisoformat(date_value)
            start_clock = time.fromisoformat(time_value)
            duration = int(duration_value)

            if selected_date < today:
                raise ValueError(
                    "Không thể chọn ngày đã qua."
                )

            if time_value not in time_options:
                raise ValueError(
                    "Giờ bắt đầu không hợp lệ."
                )

            if duration not in [d[0] for d in DURATIONS]:
                raise ValueError(
                    "Thời lượng không hợp lệ."
                )

            tz = timezone.get_current_timezone()

            start_dt = timezone.make_aware(
                datetime.combine(
                    selected_date,
                    start_clock,
                ),
                tz,
            )

            end_dt = start_dt + timedelta(
                minutes=duration
            )

            if start_dt <= timezone.now():
                raise ValueError(
                    "Giờ đã chọn đã qua. Vui lòng chọn giờ khác."
                )

            if (
                end_dt.date() != selected_date
                or end_dt.hour * 60 + end_dt.minute > 1380
            ):
                raise ValueError(
                    "Giờ kết thúc không được quá 23:00."
                )

            end_clock = end_dt.time().replace(
                second=0,
                microsecond=0,
            )

            # ==================================================
            # 4. LẤY CÁC SÂN THUỘC MÔN ĐÃ CHỌN
            # ==================================================

            courts = (
                Court.objects.filter(
                    facility__in=facilities,
                    sport_type__slug=sport,
                    status=Court.Status.ACTIVE,
                )
                .select_related(
                    "facility",
                    "sport_type",
                )
                .order_by(
                    "facility__name",
                    "name",
                )
            )

            # ==================================================
            # 5. LOẠI SÂN ĐÃ ĐƯỢC ĐẶT
            # ==================================================

            occupied_ids = Booking.objects.filter(
                court__in=courts,
                status__in=OCCUPIED_STATUSES,
                start_time__lt=end_dt,
                end_time__gt=start_dt,
            ).values_list(
                "court_id",
                flat=True,
            )

            # ==================================================
            # 6. LOẠI SÂN BỊ KHÓA
            # ==================================================

            blocked_ids = CourtBlock.objects.filter(
                court__in=courts,
                start_time__lt=end_dt,
                end_time__gt=start_dt,
            ).values_list(
                "court_id",
                flat=True,
            )

            courts = courts.exclude(
                pk__in=occupied_ids
            ).exclude(
                pk__in=blocked_ids
            )

            # ==================================================
            # 7. GOM KẾT QUẢ THEO CƠ SỞ
            # ==================================================

            available_facilities = {}

            for court in courts:

                # Kiểm tra giờ hoạt động nếu đã cấu hình.
                operating_hours = OperatingHour.objects.filter(
                    court=court,
                    day_of_week=selected_date.weekday(),
                )

                if operating_hours.exists():

                    is_open = operating_hours.filter(
                        is_closed=False,
                        open_time__lte=start_clock,
                        close_time__gte=end_clock,
                    ).exists()

                    if not is_open:
                        continue

                # Kiểm tra khả năng đặt và bảng giá.
                booking_data, booking_error = calculate_booking(
                    court,
                    selected_date,
                    start_clock,
                    end_clock,
                )

                if booking_error or not booking_data:
                    continue

                facility = court.facility

                # Mỗi cơ sở chỉ xuất hiện một lần.
                if facility.pk not in available_facilities:

                    available_facilities[facility.pk] = {
                        "facility": facility,
                        "sport": court.sport_type,
                        "available_count": 0,
                    }

                # Đếm số sân còn trống tại cơ sở.
                available_facilities[
                    facility.pk
                ]["available_count"] += 1

            results = list(
                available_facilities.values()
            )

        except (ValueError, TypeError) as exc:
            error = str(exc)

    # ==================================================
    # 8. TRẢ KẾT QUẢ VỀ TRANG CHỦ
    # ==================================================

    return render(
        request,
        "facilities/home.html",
        {
            "facilities": facilities,
            "keyword": keyword,
            "sport": sport,
            "sports": sports,
            "today": today,
            "selected_date": date_value or today.isoformat(),
            "selected_time": time_value,
            "selected_duration": duration_value,
            "time_options": time_options,
            "durations": DURATIONS,
            "has_search": has_search,
            "results": results,
            "error": error,
        },
    )
