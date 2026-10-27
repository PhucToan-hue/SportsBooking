
from datetime import datetime, timedelta, date, time
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Sum, Prefetch, ProtectedError
from django.http import HttpResponseNotAllowed
from django.shortcuts import (
    render, redirect, get_object_or_404
)
from django.utils import timezone

from facilities.models import Facility
from courts.models import (
    Court, SportType, CourtPrice, CourtBlock
)
from bookings.models import Booking
from payments.models import Payment


# =====================================================
# PHÂN QUYỀN CHỦ SÂN
# =====================================================

def owner_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if (
            not request.user.is_active
            or getattr(request.user, "role", None) != "OWNER"
        ):
            raise PermissionDenied(
                "Chỉ chủ sân được truy cập khu vực này."
            )
        return view_func(request, *args, **kwargs)

    return wrapper


def owner_facilities(request):
    return Facility.objects.filter(owner=request.user)


def owner_courts(request):
    return Court.objects.filter(
        facility__owner=request.user
    )


def owner_bookings(request):
    return Booking.objects.filter(
        court__facility__owner=request.user
    )


def get_owned_court(request, court_id):
    return get_object_or_404(
        owner_courts(request),
        pk=court_id
    )


def active_booking_queryset(court):
    return Booking.objects.filter(
        court=court
    ).exclude(
        status__in=[
            Booking.Status.CANCELLED,
            Booking.Status.REJECTED,
            Booking.Status.EXPIRED,
        ]
    )


def parse_optional_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def parse_datetime_local(value):
    result = datetime.fromisoformat(value)
    if timezone.is_naive(result):
        result = timezone.make_aware(
            result,
            timezone.get_current_timezone()
        )
    return result


def get_court_form_data(request):
    """
    Đọc và kiểm tra dữ liệu từ popup thêm/sửa sân.
    Chỉ cho chọn cơ sở thuộc chủ sân đăng nhập.
    """
    errors = []

    facility_id = request.POST.get("facility", "")
    sport_id = request.POST.get("sport_type", "")
    name = request.POST.get("name", "").strip()
    surface = request.POST.get("surface_type", "").strip()
    description = request.POST.get("description", "").strip()
    capacity_text = request.POST.get("capacity", "").strip()
    status = request.POST.get(
        "status", Court.Status.ACTIVE
    )

    facility = None
    sport = None
    capacity = None

    if facility_id.isdigit():
        facility = owner_facilities(request).filter(
            pk=int(facility_id)
        ).first()

    if not facility:
        errors.append("Cơ sở không hợp lệ.")

    if sport_id.isdigit():
        sport = SportType.objects.filter(
            pk=int(sport_id)
        ).first()

    if not sport:
        errors.append("Môn thể thao không hợp lệ.")

    if not name:
        errors.append("Vui lòng nhập tên sân.")

    if len(name) > 100:
        errors.append("Tên sân không được quá 100 ký tự.")

    if len(surface) > 100:
        errors.append(
            "Loại mặt sân không được quá 100 ký tự."
        )

    if capacity_text:
        try:
            capacity = int(capacity_text)
            if capacity <= 0:
                errors.append(
                    "Sức chứa phải lớn hơn 0."
                )
        except ValueError:
            errors.append(
                "Sức chứa phải là số nguyên."
            )

    valid_statuses = {
        Court.Status.ACTIVE,
        Court.Status.INACTIVE,
        Court.Status.MAINTENANCE,
    }

    if status not in valid_statuses:
        errors.append("Trạng thái sân không hợp lệ.")

    return {
        "facility": facility,
        "sport_type": sport,
        "name": name,
        "surface_type": surface,
        "description": description,
        "capacity": capacity,
        "status": status,
    }, errors


# =====================================================
# DASHBOARD - GIỮ NGUYÊN
# =====================================================

@owner_required
def dashboard_view(request):
    facilities = owner_facilities(request)
    courts = owner_courts(request)
    bookings = owner_bookings(request)

    today = timezone.localdate()

    confirmed = bookings.filter(
        status__in=[
            Booking.Status.CONFIRMED,
            Booking.Status.COMPLETED,
        ]
    )

    total_revenue = (
        confirmed.aggregate(
            total=Sum("total_amount")
        )["total"] or 0
    )

    context = {
        "total_facilities": facilities.count(),
        "total_courts": courts.count(),
        "active_courts": courts.filter(
            status=Court.Status.ACTIVE
        ).count(),
        "total_bookings": bookings.count(),
        "today_bookings": bookings.filter(
            start_time__date=today
        ).count(),
        "pending_bookings": bookings.filter(
            status=Booking.Status.PENDING_APPROVAL
        ).count(),
        "confirmed_bookings": confirmed.count(),
        "total_revenue": total_revenue,
        "recent_bookings": bookings.select_related(
            "customer",
            "court",
            "court__facility"
        ).order_by("-created_at")[:10],
    }

    return render(
        request,
        "owner_dashboard/dashboard.html",
        context
    )


# =====================================================
# DANH SÁCH CƠ SỞ - GIỮ NGUYÊN
# =====================================================

@owner_required
def facility_list_view(request):
    facilities = owner_facilities(
        request
    ).order_by("name")

    return render(
        request,
        "owner_dashboard/facility_list.html",
        {"facilities": facilities}
    )


# =====================================================
# DANH SÁCH SÂN
# =====================================================

@owner_required
def court_list_view(request):
    courts = owner_courts(request).select_related(
        "facility", "sport_type"
    )

    facility_id = request.GET.get("facility", "")
    sport_slug = request.GET.get("sport", "")

    if facility_id.isdigit():
        courts = courts.filter(
            facility_id=int(facility_id)
        )

    if sport_slug:
        courts = courts.filter(
            sport_type__slug=sport_slug
        )

    context = {
        "courts": courts.order_by(
            "facility__name", "name"
        ),
        "facilities": owner_facilities(
            request
        ).order_by("name"),
        "sport_types": SportType.objects.order_by(
            "name"
        ),
        "selected_facility": facility_id,
        "selected_sport": sport_slug,
    }

    return render(
        request,
        "owner_dashboard/court_list.html",
        context
    )


# =====================================================
# THÊM SÂN
# =====================================================

@owner_required
def court_add_view(request):
    if request.method != "POST":
        return redirect("owner_dashboard:court_list")

    data, errors = get_court_form_data(request)

    if data["facility"] and data["name"]:
        if Court.objects.filter(
            facility=data["facility"],
            name__iexact=data["name"]
        ).exists():
            errors.append(
                "Cơ sở này đã có sân trùng tên."
            )

    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect("owner_dashboard:court_list")

    try:
        with transaction.atomic():
            Court.objects.create(**data)

        messages.success(
            request,
            "Đã thêm sân mới thành công."
        )

    except IntegrityError:
        messages.error(
            request,
            "Không thể thêm sân. "
            "Tên sân có thể đã tồn tại."
        )

    return redirect("owner_dashboard:court_list")


# =====================================================
# SỬA SÂN
# =====================================================

@owner_required
def court_edit_view(request, court_id):
    if request.method != "POST":
        return redirect("owner_dashboard:court_list")

    court = get_owned_court(request, court_id)
    data, errors = get_court_form_data(request)

    if data["facility"] and data["name"]:
        duplicate = Court.objects.filter(
            facility=data["facility"],
            name__iexact=data["name"]
        ).exclude(pk=court.pk).exists()

        if duplicate:
            errors.append(
                "Tên sân đã tồn tại trong cơ sở."
            )

    if (
        data["status"] != Court.Status.ACTIVE
        and court.status == Court.Status.ACTIVE
        and active_booking_queryset(court).filter(
            end_time__gt=timezone.now()
        ).exists()
    ):
        errors.append(
            "Sân còn đơn đặt chưa kết thúc. "
            "Không thể ngừng hoạt động lúc này."
        )

    # Không cho chuyển sân đã có đơn đặt
    # sang cơ sở hoặc môn thể thao khác.
    if Booking.objects.filter(court=court).exists():
        if (
            data["facility"] != court.facility
            or data["sport_type"] != court.sport_type
        ):
            errors.append(
                "Sân đã có lịch sử đặt. "
                "Không thể đổi cơ sở hoặc môn thể thao."
            )

    if errors:
        for error in errors:
            messages.error(request, error)
        return redirect("owner_dashboard:court_list")

    for field, value in data.items():
        setattr(court, field, value)

    try:
        with transaction.atomic():
            court.save()

        messages.success(
            request,
            "Đã cập nhật thông tin sân."
        )

    except IntegrityError:
        messages.error(
            request,
            "Không thể lưu vì thông tin sân bị trùng."
        )

    return redirect("owner_dashboard:court_list")


# =====================================================
# XÓA SÂN AN TOÀN
# =====================================================

@owner_required
def court_delete_view(request, court_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    court = get_owned_court(request, court_id)

    if Booking.objects.filter(court=court).exists():
        messages.error(
            request,
            "Sân đã có lịch sử đặt nên không thể xóa. "
            "Bạn có thể chuyển sang Ngừng hoạt động."
        )
        return redirect("owner_dashboard:court_list")

    try:
        with transaction.atomic():
            court.delete()

        messages.success(
            request,
            "Đã xóa sân thành công."
        )

    except ProtectedError:
        messages.error(
            request,
            "Không thể xóa sân vì còn dữ liệu liên quan."
        )

    return redirect("owner_dashboard:court_list")


# =====================================================
# KHÓA TOÀN SÂN / MỞ HOẠT ĐỘNG
# =====================================================

@owner_required
def court_status_view(request, court_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    court = get_owned_court(request, court_id)

    new_status = request.POST.get("status", "")

    valid_statuses = {
        Court.Status.ACTIVE,
        Court.Status.INACTIVE,
        Court.Status.MAINTENANCE,
    }

    if new_status not in valid_statuses:
        messages.error(
            request,
            "Trạng thái không hợp lệ."
        )
        return redirect("owner_dashboard:court_list")

    if new_status != Court.Status.ACTIVE:
        has_future_booking = (
            active_booking_queryset(court)
            .filter(end_time__gt=timezone.now())
            .exists()
        )

        if has_future_booking:
            messages.error(
                request,
                "Sân đang có lịch đặt chưa kết thúc. "
                "Hãy xử lý đơn trước khi khóa toàn sân."
            )
            return redirect(
                "owner_dashboard:court_list"
            )

    court.status = new_status
    court.save(update_fields=[
        "status", "updated_at"
    ])

    messages.success(
        request,
        "Đã cập nhật trạng thái sân."
    )

    return redirect("owner_dashboard:court_list")


# =====================================================
# QUẢN LÝ BẢNG GIÁ
# =====================================================

@owner_required
def court_price_manage_view(request, court_id):
    court = get_owned_court(request, court_id)

    if request.method == "POST":
        action = request.POST.get("action", "save")

        if action == "delete":
            price = get_object_or_404(
                CourtPrice,
                pk=request.POST.get("price_id"),
                court=court
            )
            price.delete()

            messages.success(
                request,
                "Đã xóa bảng giá."
            )
            return redirect(
                "owner_dashboard:court_price_manage",
                court_id=court.pk
            )

        try:
            price_id = request.POST.get(
                "price_id", ""
            ).strip()

            day_of_week = int(
                request.POST.get("day_of_week", "")
            )
            start_time = time.fromisoformat(
                request.POST.get("start_time", "")
            )
            end_time = time.fromisoformat(
                request.POST.get("end_time", "")
            )
            price_per_hour = Decimal(
                request.POST.get("price_per_hour", "")
            )
            effective_from = date.fromisoformat(
                request.POST.get("effective_from", "")
            )
            effective_to = parse_optional_date(
                request.POST.get("effective_to", "")
            )
            is_active = (
                request.POST.get("is_active") == "on"
            )

        except (
            ValueError,
            TypeError,
            ArithmeticError,
        ):
            messages.error(
                request,
                "Thông tin bảng giá không hợp lệ."
            )
            return redirect(
                "owner_dashboard:court_price_manage",
                court_id=court.pk
            )

        if day_of_week not in range(7):
            messages.error(
                request,
                "Thứ trong tuần phải từ 0 đến 6."
            )
            return redirect(
                "owner_dashboard:court_price_manage",
                court_id=court.pk
            )

        if start_time >= end_time:
            messages.error(
                request,
                "Giờ kết thúc phải sau giờ bắt đầu."
            )
            return redirect(
                "owner_dashboard:court_price_manage",
                court_id=court.pk
            )

        if (
            not price_per_hour.is_finite()
            or price_per_hour <= 0
        ):
            messages.error(
                request,
                "Giá thuê phải là số dương hợp lệ."
            )
            return redirect(
                "owner_dashboard:court_price_manage",
                court_id=court.pk
            )

        if (
            effective_to
            and effective_to < effective_from
        ):
            messages.error(
                request,
                "Ngày hết hiệu lực không hợp lệ."
            )
            return redirect(
                "owner_dashboard:court_price_manage",
                court_id=court.pk
            )

        price = None

        if price_id:
            price = get_object_or_404(
                CourtPrice,
                pk=price_id,
                court=court
            )

        # Kiểm tra bảng giá trùng thứ, giờ,
        # khoảng ngày hiệu lực.
        if is_active:
            existing_prices = CourtPrice.objects.filter(
                court=court,
                day_of_week=day_of_week,
                is_active=True,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )

            if price:
                existing_prices = existing_prices.exclude(
                    pk=price.pk
                )

            for existing in existing_prices:
                dates_overlap = (
                    (
                        effective_to is None
                        or existing.effective_from <= effective_to
                    )
                    and (
                        existing.effective_to is None
                        or effective_from <= existing.effective_to
                    )
                )

                if dates_overlap:
                    messages.error(
                        request,
                        "Bảng giá bị trùng giờ hoặc "
                        "thời gian hiệu lực."
                    )
                    return redirect(
                        "owner_dashboard:court_price_manage",
                        court_id=court.pk
                    )

        if price is None:
            price = CourtPrice(court=court)

        price.day_of_week = day_of_week
        price.start_time = start_time
        price.end_time = end_time
        price.price_per_hour = price_per_hour
        price.effective_from = effective_from
        price.effective_to = effective_to
        price.is_active = is_active

        try:
            price.full_clean()
            price.save()
            messages.success(
                request,
                "Đã lưu bảng giá thành công."
            )
        except Exception as exc:
            messages.error(
                request,
                f"Không thể lưu bảng giá: {exc}"
            )

        return redirect(
            "owner_dashboard:court_price_manage",
            court_id=court.pk
        )

    prices = CourtPrice.objects.filter(
        court=court
    ).order_by(
        "day_of_week",
        "start_time",
        "effective_from"
    )

    return render(
        request,
        "owner_dashboard/price_manage.html",
        {
            "court": court,
            "prices": prices,
            "weekdays": [
                (0, "Thứ Hai"),
                (1, "Thứ Ba"),
                (2, "Thứ Tư"),
                (3, "Thứ Năm"),
                (4, "Thứ Sáu"),
                (5, "Thứ Bảy"),
                (6, "Chủ Nhật"),
            ],
        }
    )


# =====================================================
# KHÓA GIỜ / MỞ KHÓA GIỜ
# =====================================================

@owner_required
def court_block_manage_view(request, court_id):
    court = get_owned_court(request, court_id)

    if request.method == "POST":
        action = request.POST.get("action", "add")

        if action == "delete":
            block = get_object_or_404(
                CourtBlock,
                pk=request.POST.get("block_id"),
                court=court
            )
            block.delete()

            messages.success(
                request,
                "Đã mở khóa khung giờ."
            )
            return redirect(
                "owner_dashboard:court_block_manage",
                court_id=court.pk
            )

        try:
            start_time = parse_datetime_local(
                request.POST.get("start_time", "")
            )
            end_time = parse_datetime_local(
                request.POST.get("end_time", "")
            )
        except (ValueError, TypeError):
            messages.error(
                request,
                "Ngày giờ khóa sân không hợp lệ."
            )
            return redirect(
                "owner_dashboard:court_block_manage",
                court_id=court.pk
            )

        reason = request.POST.get(
            "reason", ""
        ).strip()

        if start_time >= end_time:
            messages.error(
                request,
                "Giờ kết thúc phải sau giờ bắt đầu."
            )
            return redirect(
                "owner_dashboard:court_block_manage",
                court_id=court.pk
            )

        if len(reason) > 255:
            messages.error(
                request,
                "Lý do không được quá 255 ký tự."
            )
            return redirect(
                "owner_dashboard:court_block_manage",
                court_id=court.pk
            )

        with transaction.atomic():
            # Khóa bản ghi sân để giảm nguy cơ
            # hai thao tác chủ sân ghi đồng thời.
            Court.objects.select_for_update().get(
                pk=court.pk
            )

            conflicting_bookings = (
                active_booking_queryset(court)
                .filter(
                    start_time__lt=end_time,
                    end_time__gt=start_time
                )
            )

            conflicting_blocks = (
                CourtBlock.objects.filter(
                    court=court,
                    start_time__lt=end_time,
                    end_time__gt=start_time
                )
            )

            if conflicting_bookings.exists():
                messages.error(
                    request,
                    "Khung giờ đã có đơn đặt. "
                    "Không thể khóa đè lên lịch khách."
                )

            elif conflicting_blocks.exists():
                messages.error(
                    request,
                    "Khung giờ này đã bị khóa."
                )

            else:
                CourtBlock.objects.create(
                    court=court,
                    start_time=start_time,
                    end_time=end_time,
                    reason=reason
                )

                messages.success(
                    request,
                    "Đã khóa khung giờ thành công."
                )

        return redirect(
            "owner_dashboard:court_block_manage",
            court_id=court.pk
        )

    blocks = CourtBlock.objects.filter(
        court=court
    ).order_by("-start_time")

    return render(
        request,
        "owner_dashboard/block_manage.html",
        {
            "court": court,
            "blocks": blocks,
        }
    )


# =====================================================
# DANH SÁCH ĐƠN ĐẶT - GIỮ NGUYÊN
# =====================================================

@owner_required
def booking_list_view(request):
    bookings = owner_bookings(request).select_related(
        "customer",
        "court",
        "court__facility"
    ).order_by("-created_at")

    status = request.GET.get("status", "")

    valid_statuses = {
        value
        for value, label in Booking.Status.choices
    }

    if status in valid_statuses:
        bookings = bookings.filter(status=status)

    return render(
        request,
        "owner_dashboard/booking_list.html",
        {
            "bookings": bookings[:100],
            "statuses": Booking.Status.choices,
            "selected_status": status,
        }
    )


# =====================================================
# LỊCH SÂN - GIỮ NGUYÊN CHỨC NĂNG CŨ
# =====================================================

@owner_required
def schedule_view(request):
    from facilities.views import (
        get_slot_price,
        OCCUPIED_STATUSES,
    )

    today = timezone.localdate()
    tz = timezone.get_current_timezone()

    facilities = owner_facilities(
        request
    ).order_by("name")

    selected_facility = request.GET.get(
        "facility", ""
    )
    selected_sport = request.GET.get(
        "sport", ""
    )

    if selected_facility.isdigit():
        facility = facilities.filter(
            pk=int(selected_facility)
        ).first()
    else:
        facility = facilities.first()

    selected_facility = (
        str(facility.pk) if facility else ""
    )

    # Cho phép xem ngày quá khứ, hiện tại,
    # tương lai trong giao diện chủ sân.
    try:
        selected_date = date.fromisoformat(
            request.GET.get("date", "")
        )
    except (ValueError, TypeError):
        selected_date = today

    is_past_date = selected_date < today
    previous_date = selected_date - timedelta(days=1)
    next_date = selected_date + timedelta(days=1)

    courts_query = Court.objects.none()

    if facility:
        courts_query = Court.objects.filter(
            facility=facility,
            status=Court.Status.ACTIVE
        ).select_related("sport_type")

        if selected_sport:
            courts_query = courts_query.filter(
                sport_type__slug=selected_sport
            )

    courts = list(
        courts_query.order_by("id")
    )

    # 05:00 - 22:00, mỗi ô 30 phút.
    minutes = list(range(300, 1320, 30))

    def to_time(value):
        return time(
            value // 60,
            value % 60
        )

    time_labels = [
        to_time(value).strftime("%H:%M")
        for value in minutes
    ]

    day_start = timezone.make_aware(
        datetime.combine(
            selected_date,
            time.min
        ),
        tz
    )

    day_end = timezone.make_aware(
        datetime.combine(
            selected_date + timedelta(days=1),
            time.min
        ),
        tz
    )

    visible_statuses = set(
        OCCUPIED_STATUSES
    )
    visible_statuses.add(
        Booking.Status.COMPLETED
    )

    court_ids = [
        court.pk for court in courts
    ]

    bookings = list(
        Booking.objects.filter(
            court_id__in=court_ids,
            status__in=visible_statuses,
            start_time__lt=day_end,
            end_time__gt=day_start,
        )
        .select_related(
            "customer", "court"
        )
        .prefetch_related(
            Prefetch(
                "payments",
                queryset=Payment.objects.order_by(
                    "id"
                ),
                to_attr="schedule_payments",
            )
        )
        .order_by("start_time", "id")
    )

    blocks = list(
        CourtBlock.objects.filter(
            court_id__in=court_ids,
            start_time__lt=day_end,
            end_time__gt=day_start,
        )
    )

    bookings_by_court = {
        court.pk: []
        for court in courts
    }

    blocks_by_court = {
        court.pk: []
        for court in courts
    }

    for booking in bookings:
        bookings_by_court[
            booking.court_id
        ].append(booking)

    for block in blocks:
        blocks_by_court[
            block.court_id
        ].append(block)

    court_rows = []

    for court in courts:
        court_bookings = bookings_by_court[
            court.pk
        ]
        court_blocks = blocks_by_court[
            court.pk
        ]

        raw_slots = []

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

            slot_end = (
                slot_start
                + timedelta(minutes=30)
            )

            matched_booking = next(
                (
                    booking
                    for booking in court_bookings
                    if (
                        booking.start_time < slot_end
                        and booking.end_time > slot_start
                    )
                ),
                None
            )

            is_blocked = any(
                (
                    block.start_time < slot_end
                    and block.end_time > slot_start
                )
                for block in court_blocks
            )

            # Tính giá cả ngày cũ.
            # Không khóa chỉ vì thời gian đã qua.
            slot_price = get_slot_price(
                court,
                selected_date,
                start_clock,
                end_clock
            )

            if matched_booking:
                status = "booked"
                reason = "Đã có khách đặt"

            elif is_blocked:
                status = "locked"
                reason = (
                    "Chủ sân đã khóa khung giờ"
                )

            elif slot_price is None:
                status = "no_price"
                reason = (
                    "Chưa có bảng giá hợp lệ"
                )

            else:
                status = "free"
                reason = (
                    "Có thể nhập lịch khách vãng lai"
                )

            booking_info = None

            if matched_booking:
                customer = matched_booking.customer

                customer_name = (
                    getattr(
                        customer,
                        "full_name",
                        ""
                    )
                    or customer.get_full_name()
                    or customer.username
                )

                customer_phone = (
                    getattr(
                        customer,
                        "phone",
                        ""
                    )
                    or "Chưa cập nhật"
                )

                paid_amount = sum(
                    (
                        payment.amount
                        for payment
                        in matched_booking.schedule_payments
                        if (
                            payment.status
                            == Payment.Status.SUCCESS
                        )
                    ),
                    Decimal("0.00")
                )

                is_paid = (
                    matched_booking.total_amount > 0
                    and paid_amount
                    >= matched_booking.total_amount
                )

                booking_info = {
                    "id": matched_booking.pk,
                    "code": matched_booking.booking_code,
                    "customer_name": customer_name,
                    "customer_phone": customer_phone,
                    "status": matched_booking.status,
                    "status_display": (
                        matched_booking.get_status_display()
                    ),
                    "start": timezone.localtime(
                        matched_booking.start_time
                    ).strftime("%H:%M"),
                    "end": timezone.localtime(
                        matched_booking.end_time
                    ).strftime("%H:%M"),
                    "total": str(
                        matched_booking.total_amount
                    ),
                    "paid": str(paid_amount),
                    "is_paid": is_paid,
                }

            raw_slots.append({
                "start": start_clock.strftime(
                    "%H:%M"
                ),
                "end": end_clock.strftime(
                    "%H:%M"
                ),
                "status": status,
                "reason": reason,
                "price": (
                    format(slot_price, "f")
                    if slot_price is not None
                    else ""
                ),
                "hourly_price": (
                    format(
                        slot_price * Decimal("2"),
                        "f"
                    )
                    if slot_price is not None
                    else ""
                ),
                "booking": booking_info,
            })

        # Gộp các ô cùng một đơn đặt.
        display_slots = []
        index = 0

        while index < len(raw_slots):
            slot = raw_slots[index]
            booking_info = slot["booking"]

            if booking_info:
                booking_id = booking_info["id"]
                span = 1

                while (
                    index + span < len(raw_slots)
                    and raw_slots[
                        index + span
                    ]["booking"]
                    and raw_slots[
                        index + span
                    ]["booking"]["id"] == booking_id
                ):
                    span += 1

                display_slots.append({
                    **slot,
                    "colspan": span,
                    "index": index,
                })

                index += span

            else:
                display_slots.append({
                    **slot,
                    "colspan": 1,
                    "index": index,
                })
                index += 1

        court_rows.append({
            "court": court,
            "slots": display_slots,
        })

    sports = []

    if facility:
        sports = (
            Court.objects.filter(
                facility=facility,
                status=Court.Status.ACTIVE
            )
            .values(
                "sport_type__slug",
                "sport_type__name"
            )
            .distinct()
            .order_by("sport_type__name")
        )

    context = {
        "facility": facility,
        "facilities": facilities,
        "courts": courts,
        "court_rows": court_rows,
        "time_labels": time_labels,
        "selected_date": selected_date,
        "today": today,
        "is_past_date": is_past_date,
        "previous_date": previous_date,
        "next_date": next_date,
        "selected_facility": selected_facility,
        "selected_sport": selected_sport,
        "sports": sports,
        "deposit_percent": 100,
    }

    return render(
        request,
        "owner_dashboard/schedule.html",
        context
    )
