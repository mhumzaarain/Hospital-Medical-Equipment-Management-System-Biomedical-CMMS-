from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied


class RoleRequiredMixin(LoginRequiredMixin):
    """Page access control. Services re-check roles independently."""

    allowed_roles: tuple = ()

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and self.allowed_roles
            and request.user.role not in self.allowed_roles
        ):
            raise PermissionDenied("Your role does not allow this page.")
        return super().dispatch(request, *args, **kwargs)
