from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

from .views import (
    UserViewSet, TagViewSet, IngredientViewSet, RecipeViewSet
)


class CustomAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
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