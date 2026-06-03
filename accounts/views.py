from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import User, Organisation
from .forms import LoginForm, UserCreateForm, UserEditForm, OrganisationForm


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(request,
                            username=form.cleaned_data['username'],
                            password=form.cleaned_data['password'])
        if user:
            login(request, user)
            return redirect('dashboard:home')
        messages.error(request, 'Invalid credentials.')
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def user_list(request):
    if not (request.user.is_op_manager or request.user.is_super_admin):
        return HttpResponseForbidden()
    if request.user.is_super_admin:
        users = User.objects.select_related('organisation').all()
    else:
        users = User.objects.filter(organisation=request.user.organisation).select_related('organisation')
    return render(request, 'accounts/user_list.html', {'users': users})


@login_required
def user_create(request):
    if not (request.user.is_op_manager or request.user.is_super_admin):
        return HttpResponseForbidden()

    # Super Admin can choose which org to add the user to
    org_id = request.GET.get('org') or request.POST.get('org')
    if request.user.is_super_admin and org_id:
        target_org = get_object_or_404(Organisation, pk=org_id)
    else:
        target_org = request.user.organisation

    form = UserCreateForm(request.POST or None, current_user=request.user)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.organisation = target_org
        user.save()
        form.save_m2m()
        messages.success(request, f'User {user.get_full_name()} created successfully.')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_form.html', {
        'form': form, 'title': 'Create User', 'target_org': target_org,
    })


@login_required
def user_edit(request, pk):
    if not (request.user.is_op_manager or request.user.is_super_admin):
        return HttpResponseForbidden()
    user = get_object_or_404(User, pk=pk, organisation=request.user.organisation)
    form = UserEditForm(request.POST or None, instance=user, current_user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'User updated.')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_form.html', {'form': form, 'title': 'Edit User', 'obj': user})


@login_required
def user_delete(request, pk):
    if not request.user.can_delete():
        return HttpResponseForbidden()
    user = get_object_or_404(User, pk=pk, organisation=request.user.organisation)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted.')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_confirm_delete.html', {'obj': user})


# ── Super Admin: Organisation management ────────────────────────────────────

@login_required
def org_list(request):
    if not request.user.is_super_admin:
        return HttpResponseForbidden()
    orgs = Organisation.objects.prefetch_related('users').all()
    return render(request, 'accounts/org_list.html', {'orgs': orgs})


@login_required
def org_create(request):
    if not request.user.is_super_admin:
        return HttpResponseForbidden()
    form = OrganisationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        org = form.save()
        messages.success(request, f'Client account "{org.name}" created.')
        return redirect('accounts:org_list')
    return render(request, 'accounts/org_form.html', {'form': form, 'title': 'Create Client Account'})


@login_required
def org_edit(request, pk):
    if not request.user.is_super_admin:
        return HttpResponseForbidden()
    org = get_object_or_404(Organisation, pk=pk)
    form = OrganisationForm(request.POST or None, instance=org)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Organisation updated.')
        return redirect('accounts:org_list')
    return render(request, 'accounts/org_form.html', {'form': form, 'title': 'Edit Client Account', 'obj': org})


@login_required
def org_suspend(request, pk):
    """Toggle active/suspended status on a client organisation."""
    if not request.user.is_super_admin:
        return HttpResponseForbidden()
    org = get_object_or_404(Organisation, pk=pk)
    if request.method == 'POST':
        org.subscription_status = 'active' if org.subscription_status == 'suspended' else 'suspended'
        org.save()
        action = 'reactivated' if org.subscription_status == 'active' else 'suspended'
        messages.success(request, f'Account "{org.name}" {action}.')
    return redirect('accounts:org_list')
