from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import User

class EmailOrPhoneBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:                                            # without this, Q(phone=None) matches users that have no phone number
            return None

        try:
            user = User.objects.get(Q(email__iexact=username.strip()) | Q(phone=username.strip()))     # iexact: Rahul@Example.com = rahul@example.com
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):      # user_can_authenticate: a deactivated user (is_active=False) cannot login
            return user
        return None