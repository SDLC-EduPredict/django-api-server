from django import forms
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict

from accounts.models import User, FacultyProfile
from accounts.otp import remove_country_code
from core.validators import otp_validator, phone_validator


# ---------------------------------------------------------------- Django admin site forms
class UserAdminCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields: tuple = ("email", "first_name", "last_name", "phone", "role")


class UserAdminChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


# ---------------------------------------------------------------- helpers
def with_current_values(instance, form_class, data) -> dict:
    # PATCH support: a ModelForm treats a missing field as "empty".
    # So we start with the values already saved and overwrite only what the client sent.
    saved = model_to_dict(instance, fields=form_class._meta.fields)
    return {**saved, **dict(data.items())}


def check_password_strength(form: forms.Form, password: str | None, user: User | None = None) -> None:
    # Uses AUTH_PASSWORD_VALIDATORS from settings.py (min length, common passwords, numeric only ...)
    if not password:
        return
    try:
        validate_password(password, user=user)
    except ValidationError as error:
        form.add_error("password", error)


# ---------------------------------------------------------------- public API forms
class RegisterForm(forms.ModelForm):
    # Public registration. Only STUDENT and FACULTY can be chosen, so nobody can register as an admin.
    role = forms.ChoiceField(choices=[(User.Role.STUDENT, "Student"), (User.Role.FACULTY, "Faculty")])
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields: tuple = ("email", "first_name", "last_name", "phone")

    def clean_email(self) -> str:
        return self.cleaned_data["email"].lower()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Password and Confirm Password do not match.")

        check_password_strength(self, password, user=User(email=cleaned_data.get("email", ""), first_name=cleaned_data.get("first_name", "")))
        return cleaned_data

    def save(self) -> User:
        data = self.cleaned_data
        # create_user() of managers.py: normalizes the email, hashes the password and saves the user.
        # A faculty account stays inactive until an admin approves it (PATCH /api/admin/users/<id>/ {"is_active": true}).
        return User.objects.create_user(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            phone=data["phone"],
            role=data["role"],
            is_active=data["role"] != User.Role.FACULTY)


class LoginForm(forms.Form):
    username = forms.CharField(label="Email or phone")
    password = forms.CharField(widget=forms.PasswordInput)


class ProfileUpdateForm(forms.ModelForm):
    # A logged-in user updating his own profile (no role, no email)
    class Meta:
        model = User
        fields: tuple = ("first_name", "last_name", "phone")


class FacultyProfileForm(forms.ModelForm):
    class Meta:
        model = FacultyProfile
        fields: tuple = ("designation", "expertise", "bio", "photo")


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput)
    password = forms.CharField(widget=forms.PasswordInput, label="New password")
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, user: User, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_old_password(self) -> str:
        old_password = self.cleaned_data["old_password"]
        if not self.user.check_password(old_password):
            raise ValidationError("Old password is incorrect.")
        return old_password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        if password and password != cleaned_data.get("confirm_password"):
            self.add_error("confirm_password", "Password and Confirm Password do not match.")
        check_password_strength(self, password, user=self.user)
        return cleaned_data

    def save(self) -> User:
        self.user.set_password(self.cleaned_data["password"])
        self.user.save(update_fields=["password"])
        return self.user


class ForgotPasswordForm(forms.Form):
    username = forms.CharField(label="Email or phone")


class VerifyPhoneOTPForm(forms.Form):
    phone = forms.CharField()
    otp = forms.CharField(validators=[otp_validator])

    def clean_phone(self) -> str:
        phone = remove_country_code(self.cleaned_data["phone"])
        phone_validator(phone)
        return phone


class VerifyEmailOTPForm(forms.Form):
    email = forms.EmailField()
    otp = forms.CharField(validators=[otp_validator])


class ResetPasswordForm(forms.Form):
    username = forms.CharField(label="Email or phone")
    otp = forms.CharField(validators=[otp_validator])
    password = forms.CharField(widget=forms.PasswordInput, label="New password")
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        if password and password != cleaned_data.get("confirm_password"):
            self.add_error("confirm_password", "Password and Confirm Password do not match.")
        check_password_strength(self, password)
        return cleaned_data


# ---------------------------------------------------------------- admin panel (React) forms
class AdminUserCreateForm(forms.ModelForm):
    # Used by the Super Admin to create users of ANY role (admin, faculty, student ...)
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields: tuple = ("email", "first_name", "last_name", "phone", "role")

    def clean_email(self) -> str:
        return self.cleaned_data["email"].lower()

    def clean(self):
        cleaned_data = super().clean()
        check_password_strength(self, cleaned_data.get("password"))
        return cleaned_data

    def save(self) -> User:
        data = self.cleaned_data
        extra_fields = {"first_name": data["first_name"], "last_name": data["last_name"], "phone": data["phone"]}

        if data["role"] == User.Role.SUPER_ADMIN:
            # create_superuser() of managers.py sets role=SUPER_ADMIN, is_staff=True, is_superuser=True
            return User.objects.create_superuser(data["email"], data["password"], **extra_fields)
        return User.objects.create_user(data["email"], data["password"], role=data["role"], **extra_fields)


class AdminUserUpdateForm(forms.ModelForm):
    # Email is not editable. Role and active status are.
    class Meta:
        model = User
        fields: tuple = ("first_name", "last_name", "phone", "role", "is_active", "email_verified")

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.apply_role_flags()
        if commit:
            user.save()
        return user