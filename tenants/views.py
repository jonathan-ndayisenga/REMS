from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.utils import timezone
from decimal import Decimal
from .models import Tenant
from .forms import TenantForm
from finance.models import LedgerEntry
from taxes.models import TaxSetting


@login_required
def tenant_list(request):
    if not request.user.can_manage_tenants():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    tenants = Tenant.objects.filter(building__in=buildings).select_related('building')
    building_filter = request.GET.get('building')
    status_filter = request.GET.get('status', 'active')
    if building_filter:
        tenants = tenants.filter(building_id=building_filter)
    if status_filter:
        tenants = tenants.filter(status=status_filter)
    return render(request, 'tenants/tenant_list.html', {
        'tenants': tenants, 'buildings': buildings,
        'building_filter': building_filter, 'status_filter': status_filter
    })


@login_required
def tenant_create(request):
    if not request.user.can_manage_tenants():
        return HttpResponseForbidden()
    form = TenantForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        tenant = form.save(commit=False)
        tenant.registered_by = request.user
        tenant.save()
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
             or request.META.get('REMOTE_ADDR')
        # Auto-create opening ledger entry
        LedgerEntry.objects.create(
            tenant=tenant,
            building=tenant.building,
            entry_date=tenant.lease_start,
            description='Opening balance — Tenant registration',
            entry_type=LedgerEntry.ENTRY_OPENING,
            debit_amount=tenant.monthly_rate,
            credit_amount=Decimal('0'),
            running_balance=tenant.monthly_rate,
            created_by=request.user,
            ip_address=ip,
        )
        messages.success(request, f'Tenant "{tenant.full_name}" registered. Ledger opened.')
        return redirect('tenants:list')
    return render(request, 'tenants/tenant_form.html', {'form': form, 'title': 'Register Tenant'})


@login_required
def tenant_detail(request, pk):
    buildings = request.user.get_buildings_qs()
    tenant = get_object_or_404(Tenant, pk=pk, building__in=buildings)
    ledger = tenant.ledger_entries.all().order_by('entry_date')
    receipts = tenant.receipts.all().order_by('-receipt_date')
    return render(request, 'tenants/tenant_detail.html', {
        'tenant': tenant, 'ledger': ledger, 'receipts': receipts,
        'balance': tenant.get_balance()
    })


@login_required
def tenant_edit(request, pk):
    if not request.user.can_manage_tenants():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    tenant = get_object_or_404(Tenant, pk=pk, building__in=buildings)
    form = TenantForm(request.POST or None, instance=tenant, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Tenant updated.')
        return redirect('tenants:detail', pk=pk)
    return render(request, 'tenants/tenant_form.html', {'form': form, 'title': 'Edit Tenant', 'obj': tenant})


@login_required
def tenant_delete(request, pk):
    if not request.user.can_delete():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    tenant = get_object_or_404(Tenant, pk=pk, building__in=buildings)
    if request.method == 'POST':
        tenant.delete()
        messages.success(request, 'Tenant removed.')
        return redirect('tenants:list')
    return render(request, 'tenants/tenant_confirm_delete.html', {'obj': tenant})


@login_required
def rent_roll(request):
    if not request.user.can_manage_tenants() and not request.user.can_access_finance():
        return HttpResponseForbidden()

    all_buildings = request.user.get_buildings_qs()
    building_filter = request.GET.get('building', '')
    date_from       = request.GET.get('date_from', '')
    date_to         = request.GET.get('date_to', '')
    status_filter   = request.GET.get('status', '')  # 'overdue' | 'settled' | ''

    tenants_qs = Tenant.objects.filter(
        building__in=all_buildings, status='active'
    ).select_related('building').order_by('building__name', 'full_name')

    if building_filter:
        tenants_qs = tenants_qs.filter(building_id=building_filter)
    if date_from:
        tenants_qs = tenants_qs.filter(lease_start__gte=date_from)
    if date_to:
        tenants_qs = tenants_qs.filter(lease_start__lte=date_to)

    rows = []
    total_monthly     = Decimal('0')
    total_outstanding = Decimal('0')

    for t in tenants_qs:
        balance = t.get_balance()
        overdue = balance > 0
        if status_filter == 'overdue' and not overdue:
            continue
        if status_filter == 'settled' and overdue:
            continue
        rows.append({'tenant': t, 'balance': balance, 'overdue': overdue})
        total_monthly += t.monthly_rate
        if overdue:
            total_outstanding += balance

    return render(request, 'tenants/rent_roll.html', {
        'rows':              rows,
        'buildings':         all_buildings,
        'building_filter':   building_filter,
        'date_from':         date_from,
        'date_to':           date_to,
        'status_filter':     status_filter,
        'total_monthly':     total_monthly,
        'total_outstanding': total_outstanding,
        'total_tenants':     len(rows),
    })


@login_required
def vacancy_report(request):
    if not request.user.can_manage_tenants() and not request.user.can_access_finance():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    building_filter = request.GET.get('building')
    if building_filter:
        buildings = buildings.filter(pk=building_filter)

    rows = []
    for b in buildings:
        occupied_rooms = set(
            Tenant.objects.filter(building=b, status='active').values_list('room_number', flat=True)
        )
        vacant_count = max(b.total_rooms - len(occupied_rooms), 0)
        rows.append({
            'building': b,
            'total_rooms': b.total_rooms,
            'occupied': len(occupied_rooms),
            'vacant': vacant_count,
            'occupancy_rate': b.occupancy_rate,
            'occupied_rooms': sorted(occupied_rooms),
        })

    all_buildings = request.user.get_buildings_qs()
    return render(request, 'tenants/vacancy_report.html', {
        'rows': rows,
        'buildings': all_buildings,
        'building_filter': building_filter,
    })


@login_required
def aged_receivables(request):
    if not request.user.can_manage_tenants() and not request.user.can_access_finance():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    building_filter = request.GET.get('building')
    qs = Tenant.objects.filter(building__in=buildings, status='active').select_related('building')
    if building_filter:
        qs = qs.filter(building_id=building_filter)

    buckets = {'0_30': [], '31_60': [], '61_90': [], '90_plus': []}
    for t in qs:
        balance = t.get_balance()
        if balance <= 0:
            continue
        days = t.days_overdue()
        row = {'tenant': t, 'balance': balance, 'days': days}
        if days <= 30:
            buckets['0_30'].append(row)
        elif days <= 60:
            buckets['31_60'].append(row)
        elif days <= 90:
            buckets['61_90'].append(row)
        else:
            buckets['90_plus'].append(row)

    total_outstanding = sum(
        r['balance'] for bucket in buckets.values() for r in bucket
    )

    return render(request, 'tenants/aged_receivables.html', {
        'buckets': buckets,
        'total_outstanding': total_outstanding,
        'buildings': request.user.get_buildings_qs(),
        'building_filter': building_filter,
    })
