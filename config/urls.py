from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', lambda r: redirect('dashboard:home')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('buildings/', include('buildings.urls', namespace='buildings')),
    path('tenants/', include('tenants.urls', namespace='tenants')),
    path('receipts/', include('receipts.urls', namespace='receipts')),
    path('expenses/', include('expenses.urls', namespace='expenses')),
    path('finance/', include('finance.urls', namespace='finance')),
    path('taxes/', include('taxes.urls', namespace='taxes')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
]
