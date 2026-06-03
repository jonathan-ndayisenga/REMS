from django import forms
from .models import Expense, ExpenseCategory
import datetime

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['building', 'category', 'expense_date', 'description', 'amount', 'payee', 'reference_no', 'notes']
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields['building'].queryset = user.get_buildings_qs()
            self.fields['category'].queryset = ExpenseCategory.objects.filter(organisation=user.organisation)
        self.fields['expense_date'].initial = datetime.date.today()
