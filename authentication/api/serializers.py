from rest_framework import serializers
from django.conf import settings
from user.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

def token_response(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh":str(refresh),
        "access_token": str(refresh.access_token),
    }

def get_or_create_google_user(email, name=""):
    """Find the user for a verified Google email, creating one on first login.

    An existing password account with the same email is linked (logged in),
    which is safe because Google has verified ownership of the address.
    """
    user = User.objects.filter(email__iexact=email).first()
    if user:
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")
        return user, False
    base = (email.split("@")[0] or "user")[:150]
    username = base
    counter = 1
    while User.objects.filter(username__iexact=username).exists():
        suffix = str(counter)
        username = base[: 150 - len(suffix)] + suffix
        counter += 1
    user = User(username=username, email=email)
    if name:
        parts = name.strip().split(None, 1)
        user.first_name = parts[0][:150]
        if len(parts) > 1:
            user.last_name = parts[1][:150]
    user.set_unusable_password()
    user.save()
    return user, True


class GoogleAuthSerializer(serializers.Serializer):
    """Verifies a Google ID token and resolves it to a local user."""
    id_token = serializers.CharField()

    def validate_id_token(self, value):
        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "")
        if not client_id:
            raise serializers.ValidationError(
                "Google sign-in is not configured on the server."
            )
        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token as google_id_token
            payload = google_id_token.verify_oauth2_token(
                value, google_requests.Request(), client_id
            )
        except Exception:
            raise serializers.ValidationError("Invalid Google ID token.")
        if not payload.get("email_verified"):
            raise serializers.ValidationError(
                "Google account email is not verified."
            )
        self.context["google_payload"] = payload
        return value

    def create(self, validated_data):
        payload = self.context["google_payload"]
        user, created = get_or_create_google_user(
            payload["email"], payload.get("name", "")
        )
        return {"user": user, "created": created}

    def to_representation(self, instance):
        user = instance["user"]
        return {
            "username": user.username,
            "email": user.email,
            "tokens": token_response(user),
        }

class UserSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        # representation.pop("id", None) this is how we can pop
        representation["tokens"] = token_response(instance)
        return representation
    
class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(
            username=data["email"],
            password=data["password"]
        )

        if not user:
            raise serializers.ValidationError("Invalid email or password.")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        return {"user": user}

    def to_representation(self, instance):
        user=instance["user"]
        return {
            "username": user.username,
            "email": user.email,
            "tokens": token_response(user)
        }
        