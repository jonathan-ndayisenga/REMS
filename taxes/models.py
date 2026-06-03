from django.db import models
from accounts.models import Organisation


class TaxSetting(models.Model):
    # receipt = deducted at point of receipting (WHT, VAT, LST)
    # income  = applied at P&L level only (RIT - Rental Income Tax)
    TYPE_RECEIPT = 'receipt'
    TYPE_INCOME  = 'income'
    TAX_TYPE_CHOICES = [
        (TYPE_RECEIPT, 'Transaction Tax (deducted on receipt)'),
        (TYPE_INCOME,  'Income Tax (applied on P&L)'),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='tax_settings')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    tax_type = models.CharField(max_length=10, choices=TAX_TYPE_CHOICES, default=TYPE_RECEIPT)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        'accounts.User', null=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.percentage}%)"

    class Meta:
        ordering = ['name']
