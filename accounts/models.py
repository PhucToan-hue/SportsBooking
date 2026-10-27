
from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Khách hàng"
        OWNER = "OWNER", "Chủ sân"
        ADMIN = "ADMIN", "Quản trị viên"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Số điện thoại"
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER
    )

    def __str__(self):
        return self.full_name or self.username


class OwnerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="owner_profile"
    )
    business_name = models.CharField(
        max_length=200,
        blank=True
    )
    verification_status = models.CharField(
        max_length=20,
        default="PENDING"
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.business_name or self.user.username


class Customer(User):
    class Meta:
        proxy = True
        verbose_name = "Khách hàng"
        verbose_name_plural = "Khách hàng"


class CourtOwner(User):
    class Meta:
        proxy = True
        verbose_name = "Quản lý sân"
        verbose_name_plural = "Quản lý sân"

