from django import forms
from .models import Receipt
from tenants.models import Tenant
import datetime

class ReceiptForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = ['tenant', 'receipt_date', 'period_month', 'period_year',
                  'gross_amount', 'payment_method', 'reference_no', 'notes']
        widgets = {
            'receipt_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            buildings = user.get_buildings_qs()
            self.fields['tenant'].queryset = Tenant.objects.filter(building__in=buildings, status='active')
        today = datetime.date.today()
        self.fields['receipt_date'].initial = today
        self.fields['period_month'].initial = today.month
        self.fields['period_year'].initial = today.year
        self.fields['period_month'].widget = forms.Select(choices=[(i, datetime.date(2000, i, 1).strftime('%B')) for i in range(1, 13)])
