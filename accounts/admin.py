from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Organisation

admin.site.register(Organisation)
admin.site.register(User, UserAdmin)
