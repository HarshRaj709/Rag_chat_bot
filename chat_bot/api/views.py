from rest_framework.views import APIView
from rest_framework.response import Response

class ChatView(APIView):
    def get(self, request):
        return Response({"message": "Chat API is working"})