import base64
import uuid

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from djoser.serializers import TokenCreateSerializer
from rest_framework import serializers

from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
    User,
    Follow
)


class CustomTokenCreateSerializer(TokenCreateSerializer):
    username = serializers.CharField(required=False)
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if email and password:
            user = User.objects.filter(email=email).first()

            if user and user.check_password(password):
                attrs['user'] = user
                return attrs

        raise serializers.ValidationError(
            {'non_field_errors': ['Неверный email или пароль']}
        )


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and 'data:image' in data:
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(
                base64.b64decode(imgstr), name=f'{uuid.uuid4()}.{ext}'
            )
        return super().to_internal_value(data)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'username', 'first_name', 'last_name', 'password']

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.password = make_password(password)
        user.save()
        return user


class UserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'email', 'id', 'username', 'first_name', 'last_name',
            'is_subscribed', 'avatar', 'recipes'
        ]

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Follow.objects.filter(user=request.user, author=obj).exists()
        return False

    def get_recipes(self, obj):
        recipes_limit = self.context.get(
            'recipes_limit',
            settings.RECIPES_LIMIT
        )
        recipes = obj.recipes.all()[:recipes_limit]
        return RecipeMinifiedSerializer(recipes, many=True).data


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'measurement_unit']


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ['id', 'name', 'image', 'cooking_time']


class IngredientInRecipeSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all()
    )

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'amount']


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(source='ingredient.measurement_unit')

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'name', 'measurement_unit', 'amount']


class RecipeListSerializer(serializers.ModelSerializer):
    tags = TagSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)
    ingredients = serializers.SerializerMethodField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            'id', 'tags', 'author', 'ingredients', 'is_favorited',
            'is_in_shopping_cart', 'name', 'image', 'text', 'cooking_time'
        ]

    def get_ingredients(self, obj):
        recipe_ingredients = obj.recipe_ingredients.all()
        return RecipeIngredientReadSerializer(recipe_ingredients, many=True).data

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user, recipe=obj
            ).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ShoppingCart.objects.filter(
                user=request.user, recipe=obj
            ).exists()
        return False


class RecipeCreateSerializer(serializers.ModelSerializer):
    image = Base64ImageField()
    ingredients = IngredientInRecipeSerializer(many=True, write_only=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, write_only=True
    )

    class Meta:
        model = Recipe
        fields = [
            'ingredients',
            'tags',
            'image',
            'name',
            'text',
            'cooking_time'
        ]

    def _save_ingredients_and_tags(self, recipe, ingredients_data, tags_data):
        recipe.recipeingredient_set.all().delete()
        recipe_ingredients = [
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient['id'],
                amount=ingredient['amount']
            )
            for ingredient in ingredients_data
        ]
        RecipeIngredient.objects.bulk_create(recipe_ingredients)

        recipe.tags.set(tags_data)

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')

        recipe = Recipe.objects.create(**validated_data)
        self._save_ingredients_and_tags(recipe, ingredients_data, tags_data)

        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        tags_data = validated_data.pop('tags')
        instance = super().update(instance, validated_data)
        self._save_ingredients_and_tags(instance, ingredients_data, tags_data)

        return instance


class AvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField()

    class Meta:
        model = User
        fields = ['avatar']


class SetPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Неверный текущий пароль")
        return value

    def validate_new_password(self, value):
        try:
            validate_password(value, self.context['request'].user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages))
        return value


class SubscribeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = []

    def validate(self, attrs):
        author = self.instance
        user = self.context['request'].user

        if author == user:
            raise serializers.ValidationError(
                {'detail': 'Нельзя подписаться на себя'}
            )

        if Follow.objects.filter(user=user, author=author).exists():
            raise serializers.ValidationError(
                {'detail': 'Вы уже подписаны на этого пользователя'}
            )

        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        author = self.instance
        Follow.objects.create(user=user, author=author)
        return author
