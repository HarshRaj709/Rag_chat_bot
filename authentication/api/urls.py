from django.urls import path
from .views import SignupView, LoginView
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView   # will handle the logout functionality by blacklisting the refresh token

urlpatterns = [
    path("register/", SignupView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", TokenBlacklistView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]