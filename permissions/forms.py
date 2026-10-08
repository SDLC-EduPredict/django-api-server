from django import forms
from accounts.models import User
from permissions.models import Permission


class RolePermissionsForm(forms.Form):
    # {"permissions": ["ADD_COURSE", "EDIT_COURSE"]}  ->  checks that every name really exists
    permissions = forms.ModelMultipleChoiceField(queryset=Permission.objects.all(), to_field_name="name", required=False)

    def __init__(self, *args, role: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role

    def save(self) -> list[str]:
        from permissions.models import RolePermission

        chosen = self.cleaned_data["permissions"]
        RolePermission.objects.filter(role=self.role).exclude(permission__in=chosen).delete()
        for permission in chosen:
            RolePermission.objects.get_or_create(role=self.role, permission=permission)
        return sorted(permission.name for permission in chosen)