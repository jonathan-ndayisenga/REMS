from django.urls import path
from . import views

app_name = 'accounts'
urlpatterns = [
    path('login/',          views.login_view,   name='login'),
    path('logout/',         views.logout_view,  name='logout'),
    path('users/',          views.user_list,    name='user_list'),
    path('users/create/',   views.user_create,  name='user_create'),
    path('users/<int:pk>/edit/',   views.user_edit,   name='user_edit'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    # Super Admin — Organisation management
    path('organisations/',                    views.org_list,    name='org_list'),
    path('organisations/create/',             views.org_create,  name='org_create'),
    path('organisations/<int:pk>/edit/',      views.org_edit,    name='org_edit'),
    path('organisations/<int:pk>/suspend/',   views.org_suspend, name='org_suspend'),
]
