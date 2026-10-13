from django.contrib.admin import AdminSite
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from .throttles import AuthThrottle


class ControlGastosAdminSite(AdminSite):
    site_header = "ControlGastos"
    site_title = "ControlGastos Admin"
    rate_action = "login"

    @method_decorator(never_cache)
    @method_decorator(csrf_protect)
    def login(self, request, extra_context=None):
        if request.method == "POST":
            throttle = AuthThrottle()
            if not throttle.allow_request(request, self):
                response = HttpResponse("Demasiados intentos. Inténtalo más tarde.", status=429)
                response["Retry-After"] = str(throttle.wait())
                return response
        return super().login(request, extra_context)


site = ControlGastosAdminSite(name="controlgastos_admin")
