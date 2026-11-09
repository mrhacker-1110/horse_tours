from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BookingViewSet, CategoryViewSet, CommentViewSet, RegisterView, TourViewSet

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('tours', TourViewSet, basename='tour')
router.register('bookings', BookingViewSet, basename='booking')
router.register('comments', CommentViewSet, basename='comment')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('', include(router.urls)),
]
