from django.urls import path
from . import views
app_name = 'tenants'
urlpatterns = [
    path('',                    views.tenant_list,       name='list'),
    path('create/',             views.tenant_create,     name='create'),
    path('<int:pk>/',           views.tenant_detail,     name='detail'),
    path('<int:pk>/edit/',      views.tenant_edit,       name='edit'),
    path('<int:pk>/delete/',    views.tenant_delete,     name='delete'),
    path('rent-roll/',          views.rent_roll,         name='rent_roll'),
    path('vacancy/',            views.vacancy_report,    name='vacancy'),
    path('aged-receivables/',   views.aged_receivables,  name='aged_receivables'),
]
