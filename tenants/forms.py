from django import forms
from .models import Tenant

class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ['building', 'full_name', 'email', 'phone', 'room_number',
                  'monthly_rate', 'lease_start', 'lease_end', 'security_deposit', 'status', 'notes']
        widgets = {
            'lease_start': forms.DateInput(attrs={'type': 'date'}),
            'lease_end':   forms.DateInput(attrs={'type': 'date'}),
            'notes':       forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['building'].queryset = user.get_buildings_qs()
