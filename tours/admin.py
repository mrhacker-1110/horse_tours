from django.contrib import admin
from .models import Booking, Category, Comment, Customer, Tour

admin.site.register([Customer, Category, Tour, Booking, Comment])
