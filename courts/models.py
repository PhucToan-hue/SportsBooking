
from django.db import models
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator
)
from facilities.models import Facility


class SportType(models.Model):
    name = models.CharField(
        max_length=50,
        unique=True
    )
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Court(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Hoạt động"
        INACTIVE = "INACTIVE", "Ngừng hoạt động"
        MAINTENANCE = "MAINTENANCE", "Bảo trì"

    facility = models.ForeignKey(
        Facility,
        on_delete=models.PROTECT,
        related_name="courts"
    )
    sport_type = models.ForeignKey(
        SportType,
        on_delete=models.PROTECT
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    surface_type = models.CharField(
        max_length=100,
        blank=True
    )
    capacity = models.PositiveIntegerField(
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "name"],
                name="unique_court_name_per_facility"
            )
        ]

    def __str__(self):
        return f"{self.facility.name} - {self.name}"


class CourtImage(models.Model):
    court = models.ForeignKey(
        Court,
        on_delete=models.CASCADE,
        related_name="images"
    )
    image = models.ImageField(
        upload_to="courts/"
    )
    is_primary = models.BooleanField(default=False)


class OperatingHour(models.Model):
    court = models.ForeignKey(
        Court,
        on_delete=models.CASCADE,
        related_name="operating_hours"
    )
    day_of_week = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(6)
        ]
    )
    open_time = models.TimeField()
    close_time = models.TimeField()
    is_closed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["court", "day_of_week"],
                name="unique_court_operating_day"
            )
        ]


class CourtPrice(models.Model):
    court = models.ForeignKey(
        Court,
        on_delete=models.CASCADE,
        related_name="prices"
    )
    day_of_week = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(6)
        ]
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    price_per_hour = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    effective_from = models.DateField()
    effective_to = models.DateField(
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)


class CourtBlock(models.Model):
    court = models.ForeignKey(
        Court,
        on_delete=models.CASCADE,
        related_name="blocks"
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    reason = models.CharField(
        max_length=255,
        blank=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )
