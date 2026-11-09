"""API-представления."""
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response

from .models import Booking, Category, Comment, Tour
from .serializers import (BookingSerializer, CategorySerializer, CommentSerializer,
                          CustomerSerializer, RegisterSerializer, TourSerializer)


class RegisterView(generics.GenericAPIView):
    """Регистрация нового клиента."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=CustomerSerializer)
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)


class CategoryViewSet(viewsets.ModelViewSet):
    """Категории туров (конный, пеший, мото...). Изменять может только админ."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class TourViewSet(viewsets.ModelViewSet):
    """Туры. Фильтр по категории: ``?category=<id>``. Изменять может только админ."""

    serializer_class = TourSerializer

    def get_queryset(self):
        qs = Tour.objects.prefetch_related('categories')
        category = self.request.query_params.get('category')
        return qs.filter(categories__id=category) if category else qs

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]


class BookingViewSet(viewsets.ModelViewSet):
    """Покупки текущего клиента."""

    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        return Booking.objects.filter(customer__user=self.request.user)


class CommentViewSet(viewsets.ModelViewSet):
    """Комментарии к турам. Фильтр: ``?tour=<id>``. Править/удалять можно только свои."""

    serializer_class = CommentSerializer
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = Comment.objects.select_related('customer__user')
        tour = self.request.query_params.get('tour')
        qs = qs.filter(tour_id=tour) if tour else qs
        if self.action == 'destroy':
            qs = qs.filter(customer__user=self.request.user)
        return qs
