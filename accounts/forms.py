from django import forms
from .models import User, UserRole, Organisation
from buildings.models import Building


class OrganisationForm(forms.ModelForm):
    class Meta:
        model = Organisation
        fields = ['name', 'contact_email', 'phone', 'address', 'subscription_status']
        widgets = {'address': forms.Textarea(attrs={'rows': 2})}


class LoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Username', 'autofocus': True}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))


class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    extra_roles = forms.MultipleChoiceField(
        choices=[], required=False, label='Additional Roles',
        widget=forms.CheckboxSelectMultiple,
        help_text='Select any additional roles beyond the primary role above.',
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'role', 'buildings', 'is_active']

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if current_user and not current_user.is_super_admin:
            allowed = [r for r in User.ROLE_CHOICES if r[0] != User.ROLE_SUPER_ADMIN]
            self.fields['role'].choices = allowed
            self.fields['extra_roles'].choices = allowed
            self.fields['buildings'].queryset = Building.objects.filter(organisation=current_user.organisation)
        else:
            self.fields['extra_roles'].choices = User.ROLE_CHOICES
            self.fields['buildings'].queryset = Building.objects.all()

    def clean(self):
        cd = super().clean()
        if cd.get('password1') != cd.get('password2'):
            raise forms.ValidationError('Passwords do not match.')
        return cd

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            self.save_m2m()
            # Save additional roles (excluding primary role to avoid duplicate)
            primary = user.role
            UserRole.objects.filter(user=user).delete()
            for role in self.cleaned_data.get('extra_roles', []):
                if role != primary:
                    UserRole.objects.get_or_create(user=user, role=role)
        return user


class UserEditForm(forms.ModelForm):
    extra_roles = forms.MultipleChoiceField(
        choices=[], required=False, label='Additional Roles',
        widget=forms.CheckboxSelectMultiple,
        help_text='Select any additional roles beyond the primary role above.',
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'role', 'buildings', 'is_active']

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if current_user and not current_user.is_super_admin:
            allowed = [r for r in User.ROLE_CHOICES if r[0] != User.ROLE_SUPER_ADMIN]
            self.fields['role'].choices = allowed
            self.fields['extra_roles'].choices = allowed
            self.fields['buildings'].queryset = Building.objects.filter(organisation=current_user.organisation)
        else:
            self.fields['extra_roles'].choices = User.ROLE_CHOICES
            self.fields['buildings'].queryset = Building.objects.all()

        # Pre-populate extra_roles with current additional roles
        if self.instance and self.instance.pk:
            current_extra = list(
                self.instance.user_roles.values_list('role', flat=True)
            )
            self.fields['extra_roles'].initial = current_extra

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            self.save_m2m()
            primary = user.role
            UserRole.objects.filter(user=user).delete()
            for role in self.cleaned_data.get('extra_roles', []):
                if role != primary:
                    UserRole.objects.get_or_create(user=user, role=role)
        return user
