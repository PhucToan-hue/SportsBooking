
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, OwnerProfile


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Thông tin bổ sung",
            {
                "fields": (
                    "full_name",
                    "phone",
                    "role",
                )
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "Thông tin bổ sung",
            {
                "fields": (
                    "email",
                    "full_name",
                    "phone",
                    "role",
                )
            },
        ),
    )

    list_display = (
        "username",
        "email",
        "full_name",
        "role",
        "is_active",
        "is_staff",
    )

    list_filter = (
        "role",
        "is_active",
        "is_staff",
    )


admin.site.register(OwnerProfile)
