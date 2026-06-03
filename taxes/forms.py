from django import forms
from .models import TaxSetting

PRESET_TAXES = [
    ('', '— Select preset or enter manually —'),
    ('Withholding Tax on Rent', 'Withholding Tax on Rent'),
    ('Rental Income Tax (RIT)', 'Rental Income Tax (RIT)'),
    ('VAT on Commercial Rent', 'VAT on Commercial Rent'),
    ('Local Service Tax (LST)', 'Local Service Tax (LST)'),
    ('Ground Rent', 'Ground Rent'),
]

class TaxSettingForm(forms.ModelForm):
    preset = forms.ChoiceField(choices=PRESET_TAXES, required=False, label='Preset Tax Type')

    class Meta:
        model = TaxSetting
        fields = ['name', 'description', 'percentage', 'tax_type', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}

    def clean(self):
        cd = super().clean()
        if cd.get('preset') and not cd.get('name'):
            cd['name'] = cd['preset']
        return cd
