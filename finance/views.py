from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db.models import Sum, Q
from decimal import Decimal
import datetime
from .models import LedgerEntry, CashbookEntry, MonthlyAccrual
from tenants.models import Tenant
from receipts.models import Receipt
from expenses.models import Expense, Supplier


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
    entries = LedgerEntry.objects.filter(
        building__in=buildings, account_type=LedgerEntry.ACCT_DEBTOR
    ).select_related('tenant', 'building')

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
def debtor_ledger(request):
    """Per-tenant debtor ledger with T-account view."""
    if not request.user.can_access_finance() and not request.user.can_manage_tenants():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    tenant_id = request.GET.get('tenant')
    building_id = request.GET.get('building')

    tenants = Tenant.objects.filter(building__in=buildings, status='active').select_related('building')
    if building_id:
        tenants = tenants.filter(building_id=building_id)

    selected_tenant = None
    entries = []
    total_dr = total_cr = balance = Decimal('0')

    if tenant_id:
        selected_tenant = get_object_or_404(Tenant, pk=tenant_id, building__in=buildings)
        entries = list(selected_tenant.ledger_entries.filter(
            account_type=LedgerEntry.ACCT_DEBTOR
        ).order_by('entry_date', 'created_at'))
        total_dr = sum(e.debit_amount  for e in entries)
        total_cr = sum(e.credit_amount for e in entries)
        balance  = total_dr - total_cr

    return render(request, 'finance/debtor_ledger.html', {
        'tenants': tenants, 'buildings': buildings,
        'selected_tenant': selected_tenant, 'entries': entries,
        'total_dr': total_dr, 'total_cr': total_cr, 'balance': balance,
        'tenant_filter': tenant_id, 'building_filter': building_id,
    })


@login_required
def creditor_ledger(request):
    """Per-supplier creditor ledger with T-account view."""
    if not request.user.can_access_finance():
        return HttpResponseForbidden()
    org = request.user.organisation
    supplier_id = request.GET.get('supplier')

    suppliers = Supplier.objects.filter(organisation=org)
    selected_supplier = None
    entries = []
    total_dr = total_cr = balance = Decimal('0')

    if supplier_id:
        selected_supplier = get_object_or_404(Supplier, pk=supplier_id, organisation=org)
        entries = list(selected_supplier.ledger_entries.filter(
            account_type=LedgerEntry.ACCT_CREDITOR
        ).order_by('entry_date', 'created_at'))
        total_dr = sum(e.debit_amount  for e in entries)
        total_cr = sum(e.credit_amount for e in entries)
        balance  = total_cr - total_dr  # creditor: CR increases liability

    return render(request, 'finance/creditor_ledger.html', {
        'suppliers': suppliers,
        'selected_supplier': selected_supplier, 'entries': entries,
        'total_dr': total_dr, 'total_cr': total_cr, 'balance': balance,
        'supplier_filter': supplier_id,
    })


@login_required
def post_monthly_charges(request):
    """UI trigger: post rent charges for a given month/year to all active tenants."""
    if not request.user.can_access_finance():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    today = datetime.date.today()

    if request.method == 'POST':
        month = int(request.POST.get('month', today.month))
        year  = int(request.POST.get('year',  today.year))
        charge_date = datetime.date(year, month, 1)
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
             or request.META.get('REMOTE_ADDR')

        tenants = Tenant.objects.filter(building__in=buildings, status='active')
        posted = skipped = 0
        for tenant in tenants:
            if MonthlyAccrual.objects.filter(tenant=tenant, period_month=month, period_year=year).exists():
                skipped += 1
                continue
            rate = tenant.monthly_rate or (tenant.building.standard_rate or Decimal('0'))
            if rate <= 0:
                skipped += 1
                continue
            prev = tenant.get_balance()
            entry = LedgerEntry.objects.create(
                tenant=tenant,
                building=tenant.building,
                account_type=LedgerEntry.ACCT_DEBTOR,
                entry_date=charge_date,
                period_month=month,
                period_year=year,
                description=f'Monthly rent charge — {charge_date.strftime("%B %Y")}',
                entry_type=LedgerEntry.ENTRY_CHARGE,
                debit_amount=rate,
                credit_amount=Decimal('0'),
                running_balance=prev + rate,
                created_by=request.user,
                ip_address=ip,
            )
            MonthlyAccrual.objects.create(
                tenant=tenant,
                period_month=month,
                period_year=year,
                expected_amount=rate,
                charge_entry=entry,
            )
            posted += 1

        messages.success(request, f'Posted charges for {charge_date.strftime("%B %Y")}: {posted} tenants charged, {skipped} skipped.')
        return redirect('finance:post_monthly_charges')

    months = [(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)]
    years  = list(range(today.year - 2, today.year + 2))
    return render(request, 'finance/post_monthly_charges.html', {
        'months': months, 'years': years,
        'current_month': today.month, 'current_year': today.year,
    })


@login_required
def vat_return(request):
    """VAT/tax return report — gross, tax, net grouped by tax type and period."""
    if not request.user.can_access_finance():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    today = datetime.date.today()
    date_from = request.GET.get('date_from', str(today.replace(month=1, day=1)))
    date_to   = request.GET.get('date_to',   str(today))

    receipts = Receipt.objects.filter(
        building__in=buildings,
        receipt_date__range=[date_from, date_to],
    ).order_by('receipt_date')

    # Aggregate by tax type from the tax_breakdown JSON
    tax_totals = {}  # {tax_name: {gross, tax, net}}
    grand_gross = grand_tax = grand_net = Decimal('0')

    for r in receipts:
        grand_gross += r.gross_amount
        grand_tax   += r.tax_deducted
        grand_net   += r.net_amount
        for tax_name, amount_str in (r.tax_breakdown or {}).items():
            amount = Decimal(str(amount_str))
            if tax_name not in tax_totals:
                tax_totals[tax_name] = {'gross': Decimal('0'), 'tax': Decimal('0'), 'net': Decimal('0'), 'count': 0}
            tax_totals[tax_name]['tax']   += amount
            tax_totals[tax_name]['count'] += 1

    # Distribute gross/net proportionally if multiple taxes
    for r in receipts:
        for tax_name in (r.tax_breakdown or {}):
            if tax_name in tax_totals:
                tax_totals[tax_name]['gross'] += r.gross_amount
                tax_totals[tax_name]['net']   += r.net_amount

    return render(request, 'finance/vat_return.html', {
        'tax_totals': tax_totals, 'receipts': receipts,
        'grand_gross': grand_gross, 'grand_tax': grand_tax, 'grand_net': grand_net,
        'date_from': date_from, 'date_to': date_to,
        'receipt_count': receipts.count(),
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
