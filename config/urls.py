
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


admin.site.site_header = (
    "HỆ THỐNG QUẢN LÝ VÀ ĐẶT SÂN THỂ THAO"
)
admin.site.site_title = "Quản lý sân thể thao"
admin.site.index_title = "TRANG QUẢN TRỊ HỆ THỐNG"


urlpatterns = [
    path("admin/", admin.site.urls),

    path("accounts/", include("accounts.urls")),

    path("payments/", include("payments.urls")),

    path("", include("facilities.urls")),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
