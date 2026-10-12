
from django.contrib import admin
from .models import (
    SportType,
    Court,
    CourtImage,
    OperatingHour,
    CourtPrice,
    CourtBlock,
)

# Đổi tên hiển thị các bảng sang tiếng Việt
SportType._meta.verbose_name = "Loại hình thể thao"
SportType._meta.verbose_name_plural = "Loại hình thể thao"

Court._meta.verbose_name = "Sân thể thao"
Court._meta.verbose_name_plural = "Danh sách sân thể thao"

CourtImage._meta.verbose_name = "Hình ảnh sân"
CourtImage._meta.verbose_name_plural = "Hình ảnh sân"

OperatingHour._meta.verbose_name = "Giờ hoạt động"
OperatingHour._meta.verbose_name_plural = "Giờ hoạt động"

CourtPrice._meta.verbose_name = "Bảng giá sân"
CourtPrice._meta.verbose_name_plural = "Bảng giá sân"

CourtBlock._meta.verbose_name = "Lịch khóa sân"
CourtBlock._meta.verbose_name_plural = "Lịch khóa sân"


# Đăng ký các bảng vào Django Admin
admin.site.register(SportType)
admin.site.register(Court)
admin.site.register(CourtImage)
admin.site.register(OperatingHour)
admin.site.register(CourtPrice)
admin.site.register(CourtBlock)
