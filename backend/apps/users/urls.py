from django.urls import path

from .views import CSRFView, ChangePasswordView, LoginView, LogoutView, MeView, ProfileView, RegisterView

urlpatterns = [
    path("auth/csrf/", CSRFView.as_view(), name="auth-csrf"),
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("users/me/", ProfileView.as_view(), name="users-me"),
]
