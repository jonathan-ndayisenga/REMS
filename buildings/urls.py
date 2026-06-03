from django.urls import path
from . import views
app_name = 'buildings'
urlpatterns = [
    path('',              views.building_list,   name='list'),
    path('create/',       views.building_create, name='create'),
    path('<int:pk>/edit/',   views.building_edit,   name='edit'),
    path('<int:pk>/delete/', views.building_delete, name='delete'),
]
