from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from decimal import Decimal
from .models import Expense, ExpenseCategory, Supplier
from .forms import ExpenseForm, SupplierForm
from finance.models import CashbookEntry, LedgerEntry


@login_required
def expense_list(request):
    if not request.user.can_expense():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    expenses = Expense.objects.filter(building__in=buildings).select_related('building', 'category', 'supplier', 'recorded_by')
    building_filter = request.GET.get('building')
    if building_filter:
        expenses = expenses.filter(building_id=building_filter)
    return render(request, 'expenses/expense_list.html', {'expenses': expenses, 'buildings': buildings, 'building_filter': building_filter})


@login_required
def expense_create(request):
    if not request.user.can_expense():
        return HttpResponseForbidden()
    form = ExpenseForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        expense = form.save(commit=False)
        expense.recorded_by = request.user
        expense.save()

        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
             or request.META.get('REMOTE_ADDR')

        # Cashbook: only the amount actually paid goes out as cash
        if expense.paid_amount > 0:
            last_cb = CashbookEntry.objects.filter(organisation=request.user.organisation).last()
            prev_bal = last_cb.balance if last_cb else Decimal('0')
            CashbookEntry.objects.create(
                organisation=request.user.organisation,
                building=expense.building,
                entry_date=expense.expense_date,
                description=f'{expense.description} (PV-{expense.voucher_number})',
                source_type=CashbookEntry.SOURCE_EXPENSE,
                source_id=expense.pk,
                debit=Decimal('0'),
                credit=expense.paid_amount,
                balance=prev_bal - expense.paid_amount,
            )

        # Creditor ledger: post full invoice as liability (CR supplier), payment as DR
        if expense.supplier:
            # CR supplier account — liability created (full invoice amount)
            prev_entries = expense.supplier.ledger_entries.order_by('-created_at').first()
            prev_bal = prev_entries.running_balance if prev_entries else Decimal('0')
            inv_balance = prev_bal + expense.amount  # creditor: CR increases balance
            LedgerEntry.objects.create(
                supplier=expense.supplier,
                building=expense.building,
                account_type=LedgerEntry.ACCT_CREDITOR,
                entry_date=expense.expense_date,
                period_month=expense.expense_date.month,
                period_year=expense.expense_date.year,
                description=f'Invoice — {expense.description} (PV-{expense.voucher_number})',
                entry_type=LedgerEntry.ENTRY_OPENING,
                debit_amount=Decimal('0'),
                credit_amount=expense.amount,
                running_balance=inv_balance,
                reference=expense.voucher_number,
                created_by=request.user,
                ip_address=ip,
            )
            # DR supplier account — payment reduces liability
            if expense.paid_amount > 0:
                pay_balance = inv_balance - expense.paid_amount
                LedgerEntry.objects.create(
                    supplier=expense.supplier,
                    building=expense.building,
                    account_type=LedgerEntry.ACCT_CREDITOR,
                    entry_date=expense.expense_date,
                    period_month=expense.expense_date.month,
                    period_year=expense.expense_date.year,
                    description=f'Payment — {expense.description} (PV-{expense.voucher_number})',
                    entry_type=LedgerEntry.ENTRY_PAYMENT,
                    debit_amount=expense.paid_amount,
                    credit_amount=Decimal('0'),
                    running_balance=pay_balance,
                    reference=expense.voucher_number,
                    created_by=request.user,
                    ip_address=ip,
                )

        messages.success(request, f'Expense PV-{expense.voucher_number} recorded.')
        return redirect('expenses:list')
    return render(request, 'expenses/expense_form.html', {'form': form, 'title': 'Record Expense'})


@login_required
def expense_detail(request, pk):
    buildings = request.user.get_buildings_qs()
    expense = get_object_or_404(Expense, pk=pk, building__in=buildings)
    ledger_entries = expense.supplier.ledger_entries.filter(reference=expense.voucher_number) if expense.supplier else []
    return render(request, 'expenses/expense_detail.html', {'expense': expense, 'ledger_entries': ledger_entries})


# ── Supplier CRUD ─────────────────────────────────────────────────────────────

@login_required
def supplier_list(request):
    if not request.user.can_expense():
        return HttpResponseForbidden()
    suppliers = Supplier.objects.filter(organisation=request.user.organisation)
    return render(request, 'expenses/supplier_list.html', {'suppliers': suppliers})


@login_required
def supplier_create(request):
    if not request.user.can_expense():
        return HttpResponseForbidden()
    form = SupplierForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        supplier = form.save(commit=False)
        supplier.organisation = request.user.organisation
        supplier.save()
        messages.success(request, f'Supplier "{supplier.name}" added.')
        return redirect('expenses:supplier_list')
    return render(request, 'expenses/supplier_form.html', {'form': form, 'title': 'Add Supplier'})


@login_required
def supplier_edit(request, pk):
    if not request.user.can_expense():
        return HttpResponseForbidden()
    supplier = get_object_or_404(Supplier, pk=pk, organisation=request.user.organisation)
    form = SupplierForm(request.POST or None, instance=supplier)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Supplier updated.')
        return redirect('expenses:supplier_list')
    return render(request, 'expenses/supplier_form.html', {'form': form, 'title': 'Edit Supplier', 'obj': supplier})


@login_required
def supplier_delete(request, pk):
    if not request.user.can_delete():
        return HttpResponseForbidden()
    supplier = get_object_or_404(Supplier, pk=pk, organisation=request.user.organisation)
    if request.method == 'POST':
        supplier.delete()
        messages.success(request, 'Supplier deleted.')
        return redirect('expenses:supplier_list')
    return render(request, 'expenses/supplier_confirm_delete.html', {'obj': supplier})


@login_required
def supplier_detail(request, pk):
    if not request.user.can_expense():
        return HttpResponseForbidden()
    supplier = get_object_or_404(Supplier, pk=pk, organisation=request.user.organisation)
    expenses = supplier.expenses.select_related('building', 'category').order_by('-expense_date')
    ledger = supplier.ledger_entries.order_by('entry_date', 'created_at')
    return render(request, 'expenses/supplier_detail.html', {
        'supplier': supplier, 'expenses': expenses, 'ledger': ledger
    })
