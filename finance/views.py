from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Sum, Q
from decimal import Decimal
import datetime
from .models import LedgerEntry, CashbookEntry
from tenants.models import Tenant
from receipts.models import Receipt
from expenses.models import Expense


@login_required
def cashbook(request):
    if not request.user.can_access_finance():
        return HttpResponseForbidden()
    org = request.user.organisation
    entries = CashbookEntry.objects.filter(organisation=org).select_related('building')

    # Filters
    date_from = request.GET.get('date_from')
    date_to   = request.GET.get('date_to')
    building  = request.GET.get('building')
    if date_from:
        entries = entries.filter(entry_date__gte=date_from)
    if date_to:
        entries = entries.filter(entry_date__lte=date_to)
    if building:
        entries = entries.filter(building_id=building)

    total_debit  = entries.aggregate(t=Sum('debit'))['t']  or Decimal('0')
    total_credit = entries.aggregate(t=Sum('credit'))['t'] or Decimal('0')
    buildings = request.user.get_buildings_qs()
    return render(request, 'finance/cashbook.html', {
        'entries': entries, 'total_debit': total_debit,
        'total_credit': total_credit, 'net': total_debit - total_credit,
        'buildings': buildings,
    })


@login_required
def ledger(request):
    if not request.user.can_access_finance() and not request.user.can_manage_tenants():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    entries = LedgerEntry.objects.filter(building__in=buildings).select_related('tenant', 'building')

    tenant_id = request.GET.get('tenant')
    building_id = request.GET.get('building')
    date_from   = request.GET.get('date_from')
    date_to     = request.GET.get('date_to')

    if tenant_id:
        entries = entries.filter(tenant_id=tenant_id)
    if building_id:
        entries = entries.filter(building_id=building_id)
    if date_from:
        entries = entries.filter(entry_date__gte=date_from)
    if date_to:
        entries = entries.filter(entry_date__lte=date_to)

    tenants = Tenant.objects.filter(building__in=buildings, status='active')
    return render(request, 'finance/ledger.html', {
        'entries': entries, 'buildings': buildings, 'tenants': tenants,
        'tenant_filter': tenant_id, 'building_filter': building_id,
    })


@login_required
def trial_balance(request):
    if not request.user.can_access_finance():
        return HttpResponseForbidden()
    org = request.user.organisation
    buildings = request.user.get_buildings_qs()

    as_of = request.GET.get('as_of', str(datetime.date.today()))
    entries = CashbookEntry.objects.filter(organisation=org, entry_date__lte=as_of)

    total_income  = entries.filter(source_type='receipt').aggregate(t=Sum('debit'))['t']  or Decimal('0')
    total_expense = entries.filter(source_type='expense').aggregate(t=Sum('credit'))['t'] or Decimal('0')
    cash_balance  = total_income - total_expense

    # Rent receivable = sum of outstanding positive tenant balances
    tenants_qs = Tenant.objects.filter(building__in=buildings, status='active')
    rent_receivable = sum(max(t.get_balance(), 0) for t in tenants_qs)
    rent_receivable = Decimal(str(rent_receivable))

    # Tax payable = taxes withheld from receipts but not yet remitted
    from receipts.models import Receipt as ReceiptModel
    receipts_to_date = ReceiptModel.objects.filter(building__in=buildings, receipt_date__lte=as_of)
    tax_payable = receipts_to_date.aggregate(t=Sum('tax_deducted'))['t'] or Decimal('0')

    # Security deposits held
    security_deposits = Tenant.objects.filter(
        building__in=buildings
    ).aggregate(t=Sum('security_deposit'))['t'] or Decimal('0')

    # Build full GL account list
    accounts = [
        # Assets (Debit normal balance)
        {'name': 'Cash / Bank Account',    'debit': cash_balance,    'credit': Decimal('0'), 'type': 'asset'},
        {'name': 'Rent Receivable',         'debit': rent_receivable, 'credit': Decimal('0'), 'type': 'asset'},
        # Income (Credit normal balance)
        {'name': 'Rental Income',           'debit': Decimal('0'),    'credit': total_income,  'type': 'income'},
        # Expenses (Debit normal balance)
        {'name': 'Operating Expenses',      'debit': total_expense,   'credit': Decimal('0'), 'type': 'expense'},
        # Liabilities (Credit normal balance)
        {'name': 'Tax Payable (Withheld)',  'debit': Decimal('0'),    'credit': tax_payable,   'type': 'liability'},
        {'name': 'Security Deposits Held',  'debit': Decimal('0'),    'credit': security_deposits, 'type': 'liability'},
    ]

    total_dr = sum(a['debit']  for a in accounts)
    total_cr = sum(a['credit'] for a in accounts)

    return render(request, 'finance/trial_balance.html', {
        'accounts': accounts, 'total_dr': total_dr, 'total_cr': total_cr,
        'balanced': total_dr == total_cr, 'as_of': as_of,
    })


@login_required
def pl_account(request):
    if not request.user.can_access_finance():
        return HttpResponseForbidden()
    org = request.user.organisation

    date_from = request.GET.get('date_from', str(datetime.date.today().replace(month=1, day=1)))
    date_to   = request.GET.get('date_to',   str(datetime.date.today()))

    entries = CashbookEntry.objects.filter(organisation=org, entry_date__range=[date_from, date_to])
    income   = entries.filter(source_type='receipt').aggregate(t=Sum('debit'))['t']  or Decimal('0')
    expenses = entries.filter(source_type='expense').aggregate(t=Sum('credit'))['t'] or Decimal('0')

    gross_profit = income
    net_profit_before_tax = gross_profit - expenses

    # Apply income tax — only taxes marked as TYPE_INCOME (e.g. RIT)
    # Transaction-level taxes (WHT, VAT) are already deducted at receipt time
    from taxes.models import TaxSetting
    income_tax_rate = Decimal('0')
    income_taxes = TaxSetting.objects.filter(
        organisation=org, is_active=True, tax_type=TaxSetting.TYPE_INCOME
    )
    if income_taxes.exists():
        income_tax_rate = sum(t.percentage for t in income_taxes)

    tax_expense = (net_profit_before_tax * income_tax_rate / 100).quantize(Decimal('0.01')) if net_profit_before_tax > 0 else Decimal('0')
    net_profit_after_tax = net_profit_before_tax - tax_expense

    return render(request, 'finance/pl_account.html', {
        'income': income, 'expenses': expenses,
        'gross_profit': gross_profit,
        'net_profit_before_tax': net_profit_before_tax,
        'tax_expense': tax_expense, 'income_tax_rate': income_tax_rate,
        'income_taxes': income_taxes,
        'net_profit_after_tax': net_profit_after_tax,
        'date_from': date_from, 'date_to': date_to,
    })


@login_required
def cash_flow(request):
    """Cash Flow Statement — operating activities for a date range."""
    if not request.user.can_access_finance() and not request.user.can_manage_tenants():
        return HttpResponseForbidden()
    org = request.user.organisation
    buildings = request.user.get_buildings_qs()

    date_from = request.GET.get('date_from', str(datetime.date.today().replace(month=1, day=1)))
    date_to   = request.GET.get('date_to',   str(datetime.date.today()))
    building_filter = request.GET.get('building')

    cb_qs = CashbookEntry.objects.filter(organisation=org, entry_date__range=[date_from, date_to])
    if building_filter:
        cb_qs = cb_qs.filter(building_id=building_filter)

    # Cash inflows — receipts
    receipts_qs = cb_qs.filter(source_type='receipt').order_by('entry_date')
    total_receipts = receipts_qs.aggregate(t=Sum('debit'))['t'] or Decimal('0')

    # Cash outflows — expenses
    expenses_qs = cb_qs.filter(source_type='expense').order_by('entry_date')
    total_expenses = expenses_qs.aggregate(t=Sum('credit'))['t'] or Decimal('0')

    net_cash_flow = total_receipts - total_expenses

    # Monthly breakdown for the period
    monthly = {}
    for entry in cb_qs.order_by('entry_date'):
        key = entry.entry_date.strftime('%b %Y')
        if key not in monthly:
            monthly[key] = {'label': key, 'inflow': Decimal('0'), 'outflow': Decimal('0')}
        if entry.source_type == 'receipt':
            monthly[key]['inflow'] += entry.debit
        else:
            monthly[key]['outflow'] += entry.credit

    for m in monthly.values():
        m['net'] = m['inflow'] - m['outflow']

    return render(request, 'finance/cash_flow.html', {
        'total_receipts': total_receipts,
        'total_expenses': total_expenses,
        'net_cash_flow': net_cash_flow,
        'monthly': list(monthly.values()),
        'buildings': buildings,
        'date_from': date_from,
        'date_to': date_to,
        'building_filter': building_filter,
    })


@login_required
def balance_sheet(request):
    if not request.user.can_access_finance():
        return HttpResponseForbidden()
    org = request.user.organisation
    as_of = request.GET.get('as_of', str(datetime.date.today()))

    entries = CashbookEntry.objects.filter(organisation=org, entry_date__lte=as_of)
    total_receipts = entries.filter(source_type='receipt').aggregate(t=Sum('debit'))['t']  or Decimal('0')
    total_expenses = entries.filter(source_type='expense').aggregate(t=Sum('credit'))['t'] or Decimal('0')
    cash_balance = total_receipts - total_expenses

    # Rent receivable = sum of positive tenant balances
    buildings = request.user.get_buildings_qs()
    tenants = Tenant.objects.filter(building__in=buildings, status='active')
    rent_receivable = sum(max(t.get_balance(), 0) for t in tenants)

    total_assets = cash_balance + Decimal(str(rent_receivable))

    # Security deposits as liability
    security_deposits = Tenant.objects.filter(building__in=buildings).aggregate(t=Sum('security_deposit'))['t'] or Decimal('0')
    total_liabilities = security_deposits
    equity = total_assets - total_liabilities

    return render(request, 'finance/balance_sheet.html', {
        'cash_balance': cash_balance, 'rent_receivable': rent_receivable,
        'total_assets': total_assets, 'security_deposits': security_deposits,
        'total_liabilities': total_liabilities, 'equity': equity,
        'as_of': as_of,
    })
