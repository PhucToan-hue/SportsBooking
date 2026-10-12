
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

from courts.models import Court


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING_DEPOSIT = (
            "PENDING_DEPOSIT", "Chờ đặt cọc"
        )
        PENDING_VERIFICATION = (
            "PENDING_VERIFICATION",
            "Chờ kiểm tra tiền cọc"
        )
        PENDING_APPROVAL = (
            "PENDING_APPROVAL", "Chờ chủ sân duyệt"
        )
        CONFIRMED = "CONFIRMED", "Đã xác nhận"
        COMPLETED = "COMPLETED", "Hoàn thành"
        CANCELLED = "CANCELLED", "Đã hủy"
        REJECTED = "REJECTED", "Từ chối"
        EXPIRED = "EXPIRED", "Hết hạn"

    booking_code = models.CharField(
        max_length=30,
        unique=True
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings"
    )
    court = models.ForeignKey(
        Court,
        on_delete=models.PROTECT,
        related_name="bookings"
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    deposit_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    remaining_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING_DEPOSIT
    )
    deposit_deadline = models.DateTimeField(
        null=True,
        blank=True
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_bookings"
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True
    )
    cancel_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        indexes = [
            models.Index(
                fields=["court", "start_time", "end_time"],
                name="booking_court_time_idx"
            ),
            models.Index(
                fields=["status"],
                name="booking_status_idx"
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.start_time
            and self.end_time
            and self.start_time >= self.end_time
        ):
            raise ValidationError(
                "Giờ kết thúc phải sau giờ bắt đầu."
            )

        if (
            self.total_amount is not None
            and self.deposit_amount is not None
            and self.deposit_amount > self.total_amount
        ):
            raise ValidationError(
                "Tiền cọc không được vượt tổng tiền."
            )

        if (
            self.total_amount is not None
            and self.deposit_amount is not None
            and self.remaining_amount is not None
            and self.remaining_amount != (
                self.total_amount - self.deposit_amount
            )
        ):
            raise ValidationError(
                "Số tiền còn lại không hợp lệ."
            )

    def __str__(self):
        return self.booking_code
