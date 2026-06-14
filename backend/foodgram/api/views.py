from collections import defaultdict

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import (
    IsAuthenticated, IsAuthenticatedOrReadOnly
)
from rest_framework.response import Response

from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    ShoppingCart,
    Tag,
    User,
)
from .serializers import (
    AvatarSerializer,
    IngredientSerializer,
    RecipeCreateSerializer,
    RecipeListSerializer,
    SetPasswordSerializer,
    TagSerializer,
    UserCreateSerializer,
    UserSerializer,
)


class CustomPagination(PageNumberPagination):
    page_size_query_param = 'limit'


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def me(self, request):
        return Response(
            UserSerializer(request.user, context={'request': request}).data
        )

    @action(
        detail=False,
        methods=['put', 'delete'],
        url_path='me/avatar',
        permission_classes=[IsAuthenticated]
    )
    def avatar(self, request):
        if request.method == 'PUT':
            serializer = AvatarSerializer(
                request.user, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            if request.user.avatar:
                return Response({'avatar': request.user.avatar.url})
            else:
                return Response({'avatar': None})
        request.user.avatar.delete(save=True) if request.user.avatar else None
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request, pk=None):
        author = get_object_or_404(User, pk=pk)
        if author == request.user:
            return Response(
                {'detail': 'Нельзя подписаться на себя'}, status=400
            )
        if request.method == 'POST':
            request.user.following.add(author)
            return Response(
                UserSerializer(
                    author, context={'request': request}
                ).data, status=201
            )
        request.user.following.remove(author)
        return Response(status=204)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def subscriptions(self, request):
        queryset = request.user.following.all().order_by('id')
        page = self.paginate_queryset(queryset)

        recipes_limit = request.query_params.get('recipes_limit', 3)
        try:
            recipes_limit = int(recipes_limit)
        except (TypeError, ValueError):
            recipes_limit = 3

        serializer = UserSerializer(
            page,
            many=True,
            context={'request': request, 'recipes_limit': recipes_limit}
        )
        return self.get_paginated_response(serializer.data)

    @action(
        detail=False,
        methods=['post'],
        permission_classes=[IsAuthenticated]
    )
    def set_password(self, request):
        serializer = SetPasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class IngredientViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer


class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = CustomPagination

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RecipeCreateSerializer
        return RecipeListSerializer

    def get_queryset(self):
        queryset = Recipe.objects.all().select_related(
            'author'
        ).prefetch_related(
            'tags', 'recipeingredient_set__ingredient'
        )
        author = self.request.query_params.get('author')

        if author:
            queryset = queryset.filter(author_id=author)
        tags = self.request.query_params.getlist('tags')

        if tags:
            queryset = queryset.filter(tags__slug__in=tags).distinct()
        is_favorited = self.request.query_params.get('is_favorited')

        if is_favorited == '1' and self.request.user.is_authenticated:
            queryset = queryset.filter(favorite__user=self.request.user)

        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart'
        )

        if is_in_shopping_cart == '1' and self.request.user.is_authenticated:
            queryset = queryset.filter(shoppingcart__user=self.request.user)

        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        if request.method == 'POST':
            Favorite.objects.get_or_create(user=request.user, recipe=recipe)
            return Response(
                RecipeListSerializer(
                    recipe, context={'request': request}
                ).data, status=201
            )
        Favorite.objects.filter(user=request.user, recipe=recipe).delete()
        return Response(status=204)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)
        if request.method == 'POST':
            ShoppingCart.objects.get_or_create(
                user=request.user, recipe=recipe
            )
            return Response(RecipeListSerializer(
                recipe, context={'request': request}
            ).data, status=201)
        ShoppingCart.objects.filter(user=request.user, recipe=recipe).delete()
        return Response(status=204)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        recipes = Recipe.objects.filter(
            shoppingcart__user=request.user
        ).prefetch_related(
            'recipeingredient_set__ingredient'
        )
        ingredients = defaultdict(int)

        for recipe in recipes:
            for ri in recipe.recipeingredient_set.all():
                key = (ri.ingredient.name, ri.ingredient.measurement_unit)
                ingredients[key] += ri.amount

        lines = []
        for (name, unit), amount in sorted(ingredients.items()):
            lines.append(f"• {name} ({unit}) — {amount}")

        content = "\n".join(lines)

        response = HttpResponse(
            content, content_type='text/plain; charset=utf-8'
        )
        response[
            'Content-Disposition'
        ] = 'attachment; filename="shopping_list.txt"'
        return response

    @action(
        detail=True,
        methods=['get'],
        permission_classes=[IsAuthenticatedOrReadOnly],
        url_path='get-link'
    )
    def get_link(self, request, pk=None):
        recipe = self.get_object()

        short_link = request.build_absolute_uri(f'/recipes/{recipe.id}')

        return Response({
            'short-link': short_link
        })
