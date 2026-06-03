from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from decimal import Decimal
import datetime, json
from finance.models import CashbookEntry
from tenants.models import Tenant
from receipts.models import Receipt
from expenses.models import Expense


@login_required
def home(request):
    user = request.user

    # Only OP Manager and Super Admin see the executive dashboard
    if not (user.is_op_manager or user.is_super_admin):
        # Redirect other roles to their natural landing pages
        if user.can_manage_tenants():
            return redirect('tenants:list')
        if user.can_receipt():
            return redirect('receipts:list')
        if user.can_expense():
            return redirect('expenses:list')
        if user.can_access_finance():
            return redirect('finance:cashbook')
        return redirect('accounts:login')

    org  = user.organisation
    all_buildings = user.get_buildings_qs()
    today = datetime.date.today()

    # ── Filters ────────────────────────────────────────────────────────────
    building_filter = request.GET.get('building')
    period = request.GET.get('period', '12')  # 3, 6, 12 months or 'custom'
    try:
        period_months = int(period)
    except (ValueError, TypeError):
        period_months = 12
    if period_months not in (3, 6, 12):
        period_months = 12

    buildings = all_buildings.filter(pk=building_filter) if building_filter else all_buildings
    cb_filter = {'organisation': org}
    if building_filter:
        cb_filter['building_id'] = building_filter

    # ── KPI cards ──────────────────────────────────────────────────────────
    total_tenants  = Tenant.objects.filter(building__in=buildings, status='active').count()
    total_buildings = buildings.count()

    # Monthly income (this month)
    this_month_income = CashbookEntry.objects.filter(
        **cb_filter, source_type='receipt',
        entry_date__year=today.year, entry_date__month=today.month
    ).aggregate(t=Sum('debit'))['t'] or Decimal('0')

    # Monthly expenses
    this_month_expenses = CashbookEntry.objects.filter(
        **cb_filter, source_type='expense',
        entry_date__year=today.year, entry_date__month=today.month
    ).aggregate(t=Sum('credit'))['t'] or Decimal('0')

    # Outstanding receivables
    tenants_qs = Tenant.objects.filter(building__in=buildings, status='active')
    outstanding = sum(max(t.get_balance(), 0) for t in tenants_qs)

    # ── Revenue chart (period_months) ──────────────────────────────────────
    chart_labels = []
    chart_income = []
    chart_expenses = []
    for i in range(period_months - 1, -1, -1):
        d = (today.replace(day=1) - datetime.timedelta(days=i * 30))
        label = d.strftime('%b %Y')
        inc = CashbookEntry.objects.filter(
            **cb_filter, source_type='receipt',
            entry_date__year=d.year, entry_date__month=d.month
        ).aggregate(t=Sum('debit'))['t'] or Decimal('0')
        exp = CashbookEntry.objects.filter(
            **cb_filter, source_type='expense',
            entry_date__year=d.year, entry_date__month=d.month
        ).aggregate(t=Sum('credit'))['t'] or Decimal('0')
        chart_labels.append(label)
        chart_income.append(float(inc))
        chart_expenses.append(float(exp))

    # ── Building occupancy ─────────────────────────────────────────────────
    building_occupancy = [
        {'name': b.name, 'rate': b.occupancy_rate, 'occupied': b.occupied_rooms, 'total': b.total_rooms}
        for b in buildings
    ]

    # ── Recent receipts ────────────────────────────────────────────────────
    recent_receipts = Receipt.objects.filter(
        building__in=buildings
    ).select_related('tenant').order_by('-receipt_date')[:5]
    # keep all_buildings for the filter dropdown

    # ── Aged receivables snapshot + top 5 by arrears ──────────────────────
    aged_30  = aged_60 = aged_90 = aged_90p = 0
    arrears_list = []
    for t in tenants_qs:
        balance = t.get_balance()
        if balance <= 0:
            continue
        days = t.days_overdue()
        if days <= 30:    aged_30  += 1
        elif days <= 60:  aged_60  += 1
        elif days <= 90:  aged_90  += 1
        else:             aged_90p += 1
        arrears_list.append({'tenant': t, 'balance': balance, 'days': days})

    top5_arrears = sorted(arrears_list, key=lambda x: x['balance'], reverse=True)[:5]

    context = {
        'total_tenants': total_tenants,
        'total_buildings': total_buildings,
        'this_month_income': this_month_income,
        'this_month_expenses': this_month_expenses,
        'net_income': this_month_income - this_month_expenses,
        'outstanding': outstanding,
        'chart_labels': json.dumps(chart_labels),
        'chart_income': json.dumps(chart_income),
        'chart_expenses': json.dumps(chart_expenses),
        'building_occupancy': building_occupancy,
        'recent_receipts': recent_receipts,
        'aged_30': aged_30, 'aged_60': aged_60,
        'aged_90': aged_90, 'aged_90p': aged_90p,
        'top5_arrears': top5_arrears,
        'today': today,
        'all_buildings': all_buildings,
        'building_filter': building_filter,
        'selected_building_name': buildings.first().name if building_filter and buildings.exists() else None,
        'period': str(period_months),
    }
    return render(request, 'dashboard/home.html', context)
