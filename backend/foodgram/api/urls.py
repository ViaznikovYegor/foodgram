from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from recipes.models import User
from .views import (
    UserViewSet, TagViewSet, IngredientViewSet, RecipeViewSet
)


class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({'error': 'Email и пароль обязательны'}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Неверный email или пароль'}, status=400)

        if not user.check_password(password):
            return Response({'error': 'Неверный email или пароль'}, status=400)

        token, created = Token.objects.get_or_create(user=user)
        return Response({'auth_token': token.key})


router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'tags', TagViewSet)
router.register(r'ingredients', IngredientViewSet)
router.register(r'recipes', RecipeViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    # Авторизация
    path('auth/token/login/', CustomAuthToken.as_view()),
    path('auth/token/logout/', CustomAuthToken.as_view()),  # можно улучшить позже
    
    # Дополнительные эндпоинты
    path('users/subscriptions/', UserViewSet.as_view({'get': 'subscriptions'})),
    path('users/<int:pk>/subscribe/', UserViewSet.as_view({'post': 'subscribe', 'delete': 'subscribe'})),
    path('users/me/avatar/', UserViewSet.as_view({'put': 'avatar', 'delete': 'avatar'})),
]