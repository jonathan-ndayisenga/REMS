from django import forms
from .models import Building

class BuildingForm(forms.ModelForm):
    class Meta:
        model = Building
        fields = ['name', 'address', 'total_rooms', 'standard_rate', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 3}), 'address': forms.Textarea(attrs={'rows': 2})}
