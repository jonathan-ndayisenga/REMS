from django.db import models
from decimal import Decimal
from tenants.models import Tenant
from buildings.models import Building


class Receipt(models.Model):
    PAYMENT_CASH    = 'cash'
    PAYMENT_MOBILE  = 'mobile_money'
    PAYMENT_BANK    = 'bank_transfer'
    PAYMENT_CHEQUE  = 'cheque'
    PAYMENT_METHODS = [
        (PAYMENT_CASH,   'Cash'),
        (PAYMENT_MOBILE, 'Mobile Money'),
        (PAYMENT_BANK,   'Bank Transfer'),
        (PAYMENT_CHEQUE, 'Cheque'),
    ]

    receipt_number  = models.CharField(max_length=30, unique=True, editable=False)
    tenant          = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='receipts')
    building        = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='receipts')
    receipt_date    = models.DateField()
    period_month    = models.PositiveIntegerField(default=1)
    period_year     = models.PositiveIntegerField(default=2025)
    gross_amount    = models.DecimalField(max_digits=15, decimal_places=2)
    tax_deducted    = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    net_amount      = models.DecimalField(max_digits=15, decimal_places=2)
    payment_method  = models.CharField(max_length=20, choices=PAYMENT_METHODS, default=PAYMENT_CASH)
    reference_no    = models.CharField(max_length=100, blank=True)
    notes           = models.TextField(blank=True)
    cashier         = models.ForeignKey(
        'accounts.User', null=True, on_delete=models.SET_NULL, related_name='receipts_issued'
    )
    tax_breakdown   = models.JSONField(default=dict, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RCP-{self.receipt_number} | {self.tenant.full_name} | {self.net_amount}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self._generate_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_number():
        import time
        return str(int(time.time() * 1000000))[-10:]

    class Meta:
        ordering = ['-receipt_date', '-created_at']
