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
            buildings_qs = user.get_buildings_qs()
            self.fields['building'].queryset = buildings_qs
            # Pre-fill monthly_rate from the building's standard_rate when only one building is available
            if not self.instance.pk and buildings_qs.count() == 1:
                building = buildings_qs.first()
                if building.standard_rate:
                    self.fields['monthly_rate'].initial = building.standard_rate
