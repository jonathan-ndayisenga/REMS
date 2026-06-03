from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from decimal import Decimal
from .models import Expense, ExpenseCategory
from .forms import ExpenseForm
from finance.models import CashbookEntry


@login_required
def expense_list(request):
    if not request.user.can_expense():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    expenses = Expense.objects.filter(building__in=buildings).select_related('building', 'category', 'recorded_by')
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
            credit=expense.amount,
            balance=prev_bal - expense.amount,
        )
        messages.success(request, f'Expense PV-{expense.voucher_number} recorded.')
        return redirect('expenses:list')
    return render(request, 'expenses/expense_form.html', {'form': form, 'title': 'Record Expense'})


@login_required
def expense_detail(request, pk):
    buildings = request.user.get_buildings_qs()
    expense = get_object_or_404(Expense, pk=pk, building__in=buildings)
    return render(request, 'expenses/expense_detail.html', {'expense': expense})
