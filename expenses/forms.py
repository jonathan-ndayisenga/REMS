from django import forms
from .models import Expense, ExpenseCategory, Supplier
import datetime


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'phone', 'email', 'address', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'notes':   forms.Textarea(attrs={'rows': 2}),
        }


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'building', 'category', 'supplier', 'payee',
            'expense_date', 'description',
            'amount', 'paid_amount',
            'reference_no', 'notes',
        ]
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'notes':        forms.Textarea(attrs={'rows': 2}),
        }
        help_texts = {
            'supplier':    'Select if this supplier is registered in the system.',
            'payee':       'Use this if the supplier is not in the system.',
            'paid_amount': 'Leave 0 if not yet paid. Enter partial amount if partially paid.',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['building'].queryset  = user.get_buildings_qs()
            self.fields['category'].queryset  = ExpenseCategory.objects.filter(organisation=user.organisation)
            self.fields['supplier'].queryset  = Supplier.objects.filter(organisation=user.organisation)
        self.fields['expense_date'].initial = datetime.date.today()
        self.fields['supplier'].required = False
        self.fields['payee'].required    = False
