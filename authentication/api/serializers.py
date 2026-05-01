from rest_framework import serializers
from user.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate

def token_response(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh":str(refresh),
        "access_token": str(refresh.access_token),
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
        