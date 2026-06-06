from django.urls import path
from . import views
app_name = 'expenses'
urlpatterns = [
    path('',                          views.expense_list,      name='list'),
    path('create/',                   views.expense_create,    name='create'),
    path('<int:pk>/',                 views.expense_detail,    name='detail'),
    path('suppliers/',                views.supplier_list,     name='supplier_list'),
    path('suppliers/create/',         views.supplier_create,   name='supplier_create'),
    path('suppliers/<int:pk>/',       views.supplier_detail,   name='supplier_detail'),
    path('suppliers/<int:pk>/edit/',  views.supplier_edit,     name='supplier_edit'),
    path('suppliers/<int:pk>/delete/',views.supplier_delete,   name='supplier_delete'),
]
