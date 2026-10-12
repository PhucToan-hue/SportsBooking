
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from bookings.models import Booking


class Payment(models.Model):
    class Type(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Tiền cọc"
        BALANCE = "BALANCE", "Tiền còn lại"

    class Method(models.TextChoices):
        BANK_TRANSFER = (
            "BANK_TRANSFER", "Chuyển khoản"
        )
        CASH = "CASH", "Tiền mặt"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Chờ xác minh"
        SUCCESS = "SUCCESS", "Thành công"
        FAILED = "FAILED", "Thất bại"
        CANCELLED = "CANCELLED", "Đã hủy"

    booking = models.ForeignKey(
        Booking,
        on_delete=models.PROTECT,
        related_name="payments"
    )
    payment_type = models.CharField(
        max_length=20,
        choices=Type.choices
    )
    payment_method = models.CharField(
        max_length=30,
        choices=Method.choices
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    transaction_code = models.CharField(
        max_length=100,
        blank=True
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verified_payments"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )


class PaymentProof(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="proofs"
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    transfer_reference = models.CharField(
        max_length=100,
        blank=True
    )
    image = models.ImageField(
        upload_to="payment_proofs/",
        null=True,
        blank=True
    )
    submitted_at = models.DateTimeField(
        auto_now_add=True
    )


class Refund(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Chờ hoàn tiền"
        COMPLETED = "COMPLETED", "Đã hoàn tiền"
        REJECTED = "REJECTED", "Không hoàn tiền"

    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="refunds"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    reason = models.TextField(blank=True)
    refunded_at = models.DateTimeField(
        null=True,
        blank=True
    )
