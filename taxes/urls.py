from django.urls import path
from . import views
app_name = 'taxes'
urlpatterns = [
    path('',              views.tax_list,   name='list'),
    path('create/',       views.tax_create, name='create'),
    path('<int:pk>/edit/',   views.tax_edit,   name='edit'),
    path('<int:pk>/delete/', views.tax_delete, name='delete'),
]
