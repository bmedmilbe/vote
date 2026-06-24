from rest_framework.generics import CreateAPIView

from .serializers import UserCreateSerializer


class SignUpView(CreateAPIView):
    serializer_class = UserCreateSerializer
    