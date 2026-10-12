
import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import User


class RegisterForm(UserCreationForm):

    username = forms.CharField(
        label="Tên đăng nhập",
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nhập tên đăng nhập"
        })
    )

    full_name = forms.CharField(
        label="Họ và tên",
        min_length=2,
        max_length=150,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Nhập họ và tên"
        })
    )

    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "example@gmail.com"
        })
    )

    phone = forms.CharField(
        label="Số điện thoại",
        required=True,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ví dụ: 0912345678",
            "inputmode": "numeric",
            "maxlength": "10"
        })
    )

    password1 = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Nhập mật khẩu"
        })
    )

    password2 = forms.CharField(
        label="Xác nhận mật khẩu",
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Nhập lại mật khẩu"
        })
    )

    class Meta:
        model = User
        fields = [
            "username",
            "full_name",
            "email",
            "phone",
            "password1",
            "password2"
        ]

    # Kiểm tra họ tên
    def clean_full_name(self):
        full_name = self.cleaned_data["full_name"].strip()

        if len(full_name) < 2:
            raise ValidationError(
                "Họ và tên phải có ít nhất 2 ký tự."
            )

        return full_name

    # Kiểm tra email
    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(
            email__iexact=email
        ).exists():
            raise ValidationError(
                "Email này đã được đăng ký."
            )

        return email

    # Kiểm tra số điện thoại Việt Nam
    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()

        pattern = r"^0[35789][0-9]{8}$"

        if not re.fullmatch(pattern, phone):
            raise ValidationError(
                "Số điện thoại phải có 10 chữ số "
                "và bắt đầu bằng 03, 05, 07, 08 hoặc 09."
            )

        if User.objects.filter(phone=phone).exists():
            raise ValidationError(
                "Số điện thoại này đã được đăng ký."
            )

        return phone

    # Lưu tài khoản
    def save(self, commit=True):
        user = super().save(commit=False)

        user.email = self.cleaned_data["email"]
        user.full_name = self.cleaned_data["full_name"]
        user.phone = self.cleaned_data["phone"]

        # Không cho người dùng tự chọn quyền
        user.role = User.Role.CUSTOMER

        if commit:
            user.save()

        return user
