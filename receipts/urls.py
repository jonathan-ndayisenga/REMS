from django.urls import path
from . import views
app_name = 'receipts'
urlpatterns = [
    path('',                views.receipt_list,   name='list'),
    path('create/',         views.receipt_create, name='create'),
    path('<int:pk>/',       views.receipt_detail, name='detail'),
    path('<int:pk>/pdf/',   views.receipt_pdf,    name='pdf'),
]
