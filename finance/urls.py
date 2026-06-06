from django.urls import path
from . import views
app_name = 'finance'
urlpatterns = [
    path('cashbook/',              views.cashbook,              name='cashbook'),
    path('ledger/',                views.ledger,                name='ledger'),
    path('debtor-ledger/',         views.debtor_ledger,         name='debtor_ledger'),
    path('creditor-ledger/',       views.creditor_ledger,       name='creditor_ledger'),
    path('trial-balance/',         views.trial_balance,         name='trial_balance'),
    path('pl/',                    views.pl_account,            name='pl'),
    path('balance-sheet/',         views.balance_sheet,         name='balance_sheet'),
    path('cash-flow/',             views.cash_flow,             name='cash_flow'),
    path('post-monthly-charges/',  views.post_monthly_charges,  name='post_monthly_charges'),
    path('vat-return/',            views.vat_return,            name='vat_return'),
]
