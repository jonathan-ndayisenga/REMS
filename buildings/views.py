from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import Building
from .forms import BuildingForm


@login_required
def building_list(request):
    buildings = request.user.get_buildings_qs()
    return render(request, 'buildings/building_list.html', {'buildings': buildings})


@login_required
def building_create(request):
    if not request.user.is_op_manager and not request.user.is_super_admin:
        return HttpResponseForbidden()
    form = BuildingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        building = form.save(commit=False)
        building.organisation = request.user.organisation
        building.save()
        messages.success(request, f'Building "{building.name}" created.')
        return redirect('buildings:list')
    return render(request, 'buildings/building_form.html', {'form': form, 'title': 'Add Building'})


@login_required
def building_edit(request, pk):
    if not request.user.is_op_manager and not request.user.is_super_admin:
        return HttpResponseForbidden()
    building = get_object_or_404(Building, pk=pk, organisation=request.user.organisation)
    form = BuildingForm(request.POST or None, instance=building)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Building updated.')
        return redirect('buildings:list')
    return render(request, 'buildings/building_form.html', {'form': form, 'title': 'Edit Building', 'obj': building})


@login_required
def building_delete(request, pk):
    if not request.user.can_delete():
        return HttpResponseForbidden()
    building = get_object_or_404(Building, pk=pk, organisation=request.user.organisation)
    if request.method == 'POST':
        building.delete()
        messages.success(request, 'Building deleted.')
        return redirect('buildings:list')
    return render(request, 'buildings/building_confirm_delete.html', {'obj': building})
