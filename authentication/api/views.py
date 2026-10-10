from rest_framework.response import Response
from rest_framework.generics import CreateAPIView, ListAPIView, UpdateAPIView, DestroyAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from .serializers import UserSignupSerializer, UserLoginSerializer, GoogleAuthSerializer
from rest_framework.generics import GenericAPIView


class SignupView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserSignupSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "user": serializer.data,
            "message": "User created successfully."
        })



class LoginView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response({
            "user": serializer.data,
            "message": "User logged in successfully."
        })


class GoogleLoginView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = GoogleAuthSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response({
            "user": serializer.data,
            "message": (
                "User created successfully."
                if result["created"]
                else "User logged in successfully."
            ),
        })