from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from accounts.models import User


class UserAdminCreationForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields: tuple = ("email", "first_name", "last_name", "phone", "role")


class UserAdminChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"