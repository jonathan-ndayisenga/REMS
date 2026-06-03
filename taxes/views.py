from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import TaxSetting
from .forms import TaxSettingForm


@login_required
def tax_list(request):
    if not request.user.can_configure_taxes() and not request.user.is_op_manager:
        return HttpResponseForbidden()
    taxes = TaxSetting.objects.filter(organisation=request.user.organisation)
    return render(request, 'taxes/tax_list.html', {'taxes': taxes})


@login_required
def tax_create(request):
    if not request.user.can_configure_taxes():
        return HttpResponseForbidden()
    form = TaxSettingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        tax = form.save(commit=False)
        tax.organisation = request.user.organisation
        tax.created_by = request.user
        tax.save()
        messages.success(request, f'Tax "{tax.name}" configured.')
        return redirect('taxes:list')
    return render(request, 'taxes/tax_form.html', {'form': form, 'title': 'Add Tax Setting'})


@login_required
def tax_edit(request, pk):
    if not request.user.can_configure_taxes():
        return HttpResponseForbidden()
    tax = get_object_or_404(TaxSetting, pk=pk, organisation=request.user.organisation)
    form = TaxSettingForm(request.POST or None, instance=tax)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Tax updated.')
        return redirect('taxes:list')
    return render(request, 'taxes/tax_form.html', {'form': form, 'title': 'Edit Tax', 'obj': tax})


@login_required
def tax_delete(request, pk):
    if not request.user.can_configure_taxes():
        return HttpResponseForbidden()
    tax = get_object_or_404(TaxSetting, pk=pk, organisation=request.user.organisation)
    if request.method == 'POST':
        tax.delete()
        messages.success(request, 'Tax removed.')
        return redirect('taxes:list')
    return render(request, 'taxes/tax_confirm_delete.html', {'obj': tax})
