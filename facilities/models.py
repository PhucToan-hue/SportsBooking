
from django.db import models
from django.conf import settings


class Facility(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Chờ duyệt"
        APPROVED = "APPROVED", "Đã duyệt"
        REJECTED = "REJECTED", "Từ chối"
        SUSPENDED = "SUSPENDED", "Tạm khóa"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="facilities"
    )

    name = models.CharField(max_length=200)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    ward = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)

    image = models.ImageField(
        upload_to="facilities/",
        null=True,
        blank=True,
        verbose_name="Ảnh đại diện cơ sở"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Amenity(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name


class FacilityAmenity(models.Model):
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE
    )
    amenity = models.ForeignKey(
        Amenity,
        on_delete=models.CASCADE
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "amenity"],
                name="unique_facility_amenity"
            )
        ]

    def __str__(self):
        return f"{self.facility.name} - {self.amenity.name}"


class FacilityBankAccount(models.Model):
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name="bank_accounts"
    )

    bank_code = models.CharField(max_length=30)
    account_number = models.CharField(max_length=50)
    account_name = models.CharField(max_length=150)

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.facility.name} - {self.bank_code}"
