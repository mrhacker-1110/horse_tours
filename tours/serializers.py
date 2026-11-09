"""Сериализаторы и валидация входящих данных."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from .models import Booking, Category, Comment, Customer, Tour

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """Регистрация: создаёт User и связанного Customer (1-1)."""

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Пользователь с таким именем уже существует.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        user = User.objects.create_user(username=validated_data['username'], password=validated_data['password'])
        return Customer.objects.create(user=user, phone=validated_data.get('phone', ''))


class CustomerSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Customer
        fields = ['id', 'username', 'phone']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class TourSerializer(serializers.ModelSerializer):
    """Тур. Категории передаются списком id (многие ко многим)."""

    categories = serializers.PrimaryKeyRelatedField(many=True, queryset=Category.objects.all(), allow_empty=False)

    class Meta:
        model = Tour
        fields = ['id', 'title', 'description', 'price', 'categories']

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError('Цена должна быть больше нуля.')
        return value


class BookingSerializer(serializers.ModelSerializer):
    """Покупка тура. Клиент берётся из request.user."""

    class Meta:
        model = Booking
        fields = ['id', 'tour', 'date', 'time', 'created_at']
        read_only_fields = ['created_at']

    def validate(self, attrs):
        customer = self.context['request'].user.customer
        date, time = attrs['date'], attrs['time']
        if date < timezone.localdate():
            raise serializers.ValidationError({'date': 'Нельзя купить тур на прошедшую дату.'})
        if Booking.objects.filter(customer=customer, date=date, time=time).exists():
            raise serializers.ValidationError('У вас уже куплен тур на эту дату и время.')
        return attrs

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user.customer
        return super().create(validated_data)


class CommentSerializer(serializers.ModelSerializer):
    """Комментарий. Оставить можно только к туру, в котором клиент уже был."""

    customer = CustomerSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'tour', 'customer', 'text', 'rating', 'created_at']
        read_only_fields = ['created_at']

    def validate_text(self, value):
        if not value.strip():
            raise serializers.ValidationError('Комментарий не может быть пустым.')
        return value

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Оценка должна быть от 1 до 5.')
        return value

    def validate(self, attrs):
        customer = self.context['request'].user.customer
        attended = Booking.objects.filter(customer=customer, tour=attrs['tour'], date__lte=timezone.localdate())
        if not attended.exists():
            raise serializers.ValidationError('Комментировать можно только туры, в которых вы были.')
        return attrs

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user.customer
        return super().create(validated_data)
