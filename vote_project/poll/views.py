from rest_framework.generics import CreateAPIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import SignInSerializer, UserCreateSerializer


class SignUpView(CreateAPIView):
    serializer_class = UserCreateSerializer
class SignInView(TokenObtainPairView):
    serializer_class = SignInSerializer
    