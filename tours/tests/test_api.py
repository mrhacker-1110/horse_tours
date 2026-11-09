"""Тесты отправки данных (POST) и связей между моделями."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from tours.models import Booking, Category, Comment, Customer, Tour

User = get_user_model()
TOMORROW = (timezone.localdate() + timedelta(days=1)).isoformat()
YESTERDAY = timezone.localdate() - timedelta(days=1)


def make_customer(username='ali'):
    user = User.objects.create_user(username=username, password='StrongPass123!')
    return Customer.objects.create(user=user, phone='+996700000000')


class BaseTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.horse = Category.objects.create(name='конный')
        self.hike = Category.objects.create(name='пеший')
        self.moto = Category.objects.create(name='мото')
        self.tour1 = Tour.objects.create(title='Ущелье Ала-Арча', price='5000')
        self.tour1.categories.set([self.horse])
        self.tour2 = Tour.objects.create(title='Джети-Огуз', price='7000')
        self.tour2.categories.set([self.horse, self.hike])
        self.customer = make_customer('ali')
        self.client.force_authenticate(self.customer.user)


class RelationsTest(BaseTest):
    def test_one_to_one_user_customer(self):
        self.assertEqual(self.customer.user.customer, self.customer)

    def test_one_to_one_duplicate_customer_forbidden(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.create(user=self.customer.user)

    def test_one_to_many_tour_bookings(self):
        Booking.objects.create(customer=self.customer, tour=self.tour1, date=TOMORROW, time='10:00')
        self.assertEqual(self.tour1.bookings.count(), 1)
        self.assertEqual(self.customer.bookings.count(), 1)

    def test_many_to_many_tour_categories(self):
        self.assertEqual(self.tour2.categories.count(), 2)
        self.assertEqual(self.horse.tours.count(), 2)
        self.assertEqual(self.hike.tours.count(), 1)

    def test_category_unique_name(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(name='конный')

    def test_db_unique_customer_date_time(self):
        Booking.objects.create(customer=self.customer, tour=self.tour1, date=TOMORROW, time='10:00')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(customer=self.customer, tour=self.tour2, date=TOMORROW, time='10:00')

    def test_db_rating_check_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Comment.objects.create(customer=self.customer, tour=self.tour1, text='x', rating=9)


class RegisterTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.client.force_authenticate(None)

    def test_register_ok_creates_customer(self):
        r = self.client.post('/api/register/', {'username': 'new', 'password': 'StrongPass123!', 'phone': '+996555'})
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Customer.objects.filter(user__username='new').exists())

    def test_register_duplicate_username(self):
        r = self.client.post('/api/register/', {'username': 'ali', 'password': 'StrongPass123!'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('username', r.data)

    def test_register_weak_password(self):
        r = self.client.post('/api/register/', {'username': 'new', 'password': '123'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('password', r.data)

    def test_register_missing_fields(self):
        r = self.client.post('/api/register/', {})
        self.assertEqual(r.status_code, 400)
        self.assertIn('username', r.data)
        self.assertIn('password', r.data)


class CategoryTourTest(BaseTest):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser('admin', password='AdminPass123!')

    def test_list_tours_public(self):
        self.client.force_authenticate(None)
        r = self.client.get('/api/tours/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_filter_tours_by_category(self):
        r = self.client.get(f'/api/tours/?category={self.hike.id}')
        self.assertEqual([t['title'] for t in r.data], ['Джети-Огуз'])

    def test_create_tour_admin_ok_with_categories(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/tours/', {'title': 'Сон-Куль', 'price': '9000',
                                              'categories': [self.horse.id, self.moto.id]}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Tour.objects.get(pk=r.data['id']).categories.count(), 2)

    def test_create_tour_regular_user_forbidden(self):
        r = self.client.post('/api/tours/', {'title': 'X', 'price': '1', 'categories': [self.horse.id]}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_create_tour_anonymous_unauthorized(self):
        self.client.force_authenticate(None)
        r = self.client.post('/api/tours/', {'title': 'X', 'price': '1', 'categories': [self.horse.id]}, format='json')
        self.assertIn(r.status_code, (401, 403))

    def test_create_tour_without_categories(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/tours/', {'title': 'X', 'price': '100', 'categories': []}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('categories', r.data)

    def test_create_tour_unknown_category(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/tours/', {'title': 'X', 'price': '100', 'categories': [9999]}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_create_tour_bad_price(self):
        self.client.force_authenticate(self.admin)
        for price in ('0', '-5', 'abc'):
            r = self.client.post('/api/tours/', {'title': 'X', 'price': price, 'categories': [self.horse.id]}, format='json')
            self.assertEqual(r.status_code, 400, price)
            self.assertIn('price', r.data)

    def test_create_tour_missing_title(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/tours/', {'price': '100', 'categories': [self.horse.id]}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('title', r.data)

    def test_create_category_admin_and_duplicate(self):
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post('/api/categories/', {'name': 'верблюды'}).status_code, 201)
        self.assertEqual(self.client.post('/api/categories/', {'name': 'верблюды'}).status_code, 400)

    def test_create_category_regular_user_forbidden(self):
        self.assertEqual(self.client.post('/api/categories/', {'name': 'x'}).status_code, 403)


class BookingTest(BaseTest):
    def book(self, tour=None, date=TOMORROW, time='10:00', client=None):
        return (client or self.client).post('/api/bookings/', {'tour': (tour or self.tour1).id, 'date': date, 'time': time})

    def test_buy_tour_ok(self):
        r = self.book()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Booking.objects.get().customer, self.customer)

    def test_cannot_buy_two_tours_same_date_and_time(self):
        self.assertEqual(self.book(self.tour1).status_code, 201)
        r = self.book(self.tour2)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Booking.objects.count(), 1)

    def test_cannot_buy_same_tour_twice_same_slot(self):
        self.book()
        self.assertEqual(self.book().status_code, 400)

    def test_can_buy_same_date_different_time(self):
        self.book(time='10:00')
        self.assertEqual(self.book(self.tour2, time='14:00').status_code, 201)

    def test_can_buy_same_time_different_date(self):
        self.book(date=TOMORROW)
        other = (timezone.localdate() + timedelta(days=2)).isoformat()
        self.assertEqual(self.book(date=other).status_code, 201)

    def test_other_customer_can_buy_same_slot(self):
        self.book()
        other = APIClient()
        other.force_authenticate(make_customer('bob').user)
        self.assertEqual(self.book(client=other).status_code, 201)

    def test_past_date_rejected(self):
        r = self.book(date=YESTERDAY.isoformat())
        self.assertEqual(r.status_code, 400)
        self.assertIn('date', r.data)

    def test_invalid_formats_and_missing(self):
        self.assertEqual(self.book(date='not-a-date').status_code, 400)
        self.assertEqual(self.book(time='25:99').status_code, 400)
        self.assertEqual(self.client.post('/api/bookings/', {}).status_code, 400)

    def test_unknown_tour(self):
        r = self.client.post('/api/bookings/', {'tour': 9999, 'date': TOMORROW, 'time': '10:00'})
        self.assertEqual(r.status_code, 400)

    def test_anonymous_cannot_book(self):
        self.client.force_authenticate(None)
        self.assertIn(self.book().status_code, (401, 403))

    def test_user_sees_only_own_bookings(self):
        self.book()
        other = APIClient()
        other.force_authenticate(make_customer('bob').user)
        self.assertEqual(len(other.get('/api/bookings/').data), 0)
        self.assertEqual(len(self.client.get('/api/bookings/').data), 1)


class CommentTest(BaseTest):
    def attend(self, tour, date=YESTERDAY):
        return Booking.objects.create(customer=self.customer, tour=tour, date=date, time='10:00')

    def post(self, tour, text='Отлично!', rating=5, client=None):
        return (client or self.client).post('/api/comments/', {'tour': tour.id, 'text': text, 'rating': rating})

    def test_comment_ok_after_attending(self):
        self.attend(self.tour1)
        r = self.post(self.tour1)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['customer']['username'], 'ali')

    def test_multiple_comments_to_attended_tours(self):
        self.attend(self.tour1)
        Booking.objects.create(customer=self.customer, tour=self.tour2, date=YESTERDAY, time='15:00')
        self.assertEqual(self.post(self.tour1, 'первый').status_code, 201)
        self.assertEqual(self.post(self.tour1, 'второй').status_code, 201)
        self.assertEqual(self.post(self.tour2, 'третий').status_code, 201)
        self.assertEqual(self.customer.comments.count(), 3)

    def test_cannot_comment_tour_not_attended(self):
        r = self.post(self.tour1)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Comment.objects.count(), 0)

    def test_cannot_comment_on_future_booking(self):
        self.attend(self.tour1, date=timezone.localdate() + timedelta(days=3))
        self.assertEqual(self.post(self.tour1).status_code, 400)

    def test_cannot_comment_tour_attended_only_by_other(self):
        bob = make_customer('bob')
        Booking.objects.create(customer=bob, tour=self.tour1, date=YESTERDAY, time='10:00')
        self.assertEqual(self.post(self.tour1).status_code, 400)

    def test_empty_text(self):
        self.attend(self.tour1)
        for text in ('', '   '):
            self.assertEqual(self.post(self.tour1, text=text).status_code, 400)

    def test_rating_out_of_range(self):
        self.attend(self.tour1)
        for rating in (0, 6, -1, 'abc'):
            self.assertEqual(self.post(self.tour1, rating=rating).status_code, 400, rating)

    def test_missing_fields_and_unknown_tour(self):
        self.assertEqual(self.client.post('/api/comments/', {}).status_code, 400)
        r = self.client.post('/api/comments/', {'tour': 9999, 'text': 'x'})
        self.assertEqual(r.status_code, 400)

    def test_anonymous_cannot_comment(self):
        self.client.force_authenticate(None)
        self.assertIn(self.post(self.tour1).status_code, (401, 403))

    def test_list_and_filter_by_tour(self):
        self.attend(self.tour1)
        self.post(self.tour1)
        self.client.force_authenticate(None)
        self.assertEqual(len(self.client.get(f'/api/comments/?tour={self.tour1.id}').data), 1)
        self.assertEqual(len(self.client.get(f'/api/comments/?tour={self.tour2.id}').data), 0)

    def test_delete_only_own_comment(self):
        self.attend(self.tour1)
        cid = self.post(self.tour1).data['id']
        other = APIClient()
        other.force_authenticate(make_customer('bob').user)
        self.assertEqual(other.delete(f'/api/comments/{cid}/').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/comments/{cid}/').status_code, 204)
