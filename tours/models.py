"""Модели стартапа конных туров.

Связи:
    * один к одному     — ``User`` <-> ``Customer``
    * один ко многим    — ``Tour`` -> ``Booking``, ``Customer`` -> ``Booking``,
                          ``Customer`` -> ``Comment``, ``Tour`` -> ``Comment``
    * многие ко многим  — ``Tour`` <-> ``Category``
"""
from django.conf import settings
from django.db import models
from django.db.models import Q


class Customer(models.Model):
    """Клиент. Связь 1-1 со встроенным пользователем Django."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customer')
    phone = models.CharField('Телефон', max_length=20, blank=True)

    def __str__(self):
        return self.user.get_username()


class Category(models.Model):
    """Категория тура: «конный», «пеший», «мото» и т.д."""

    name = models.CharField('Название', max_length=50, unique=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Tour(models.Model):
    """Тур. Имеет несколько категорий (многие ко многим)."""

    title = models.CharField('Название', max_length=120)
    description = models.TextField('Описание', blank=True)
    price = models.DecimalField('Цена', max_digits=10, decimal_places=2)
    categories = models.ManyToManyField(Category, related_name='tours')

    def __str__(self):
        return self.title


class Booking(models.Model):
    """Покупка тура на конкретные дату и время.

    Ограничение: один клиент не может купить два тура на одну и ту же дату и время.
    """

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='bookings')
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='bookings')
    date = models.DateField('Дата')
    time = models.TimeField('Время')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['customer', 'date', 'time'], name='unique_customer_date_time'),
        ]

    def __str__(self):
        return f'{self.customer} - {self.tour} {self.date} {self.time}'


class Comment(models.Model):
    """Комментарий клиента к туру. Клиент может оставить несколько комментариев."""

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='comments')
    tour = models.ForeignKey(Tour, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField('Текст')
    rating = models.PositiveSmallIntegerField('Оценка', default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(rating__gte=1) & Q(rating__lte=5), name='comment_rating_1_5'),
        ]

    def __str__(self):
        return f'{self.customer} -> {self.tour}'
