from django.urls import path
from . import views
app_name = 'finance'
urlpatterns = [
    path('cashbook/',       views.cashbook,        name='cashbook'),
    path('ledger/',         views.ledger,          name='ledger'),
    path('trial-balance/',  views.trial_balance,   name='trial_balance'),
    path('pl/',             views.pl_account,      name='pl'),
    path('balance-sheet/',  views.balance_sheet,   name='balance_sheet'),
    path('cash-flow/',      views.cash_flow,       name='cash_flow'),
]
