from django.db import models
from decimal import Decimal
from buildings.models import Building


class ExpenseCategory(models.Model):
    organisation = models.ForeignKey('accounts.Organisation', on_delete=models.CASCADE, related_name='expense_categories')
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Expense Categories'
        ordering = ['name']


class Expense(models.Model):
    voucher_number  = models.CharField(max_length=30, unique=True, editable=False)
    building        = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='expenses')
    category        = models.ForeignKey(ExpenseCategory, null=True, on_delete=models.SET_NULL, related_name='expenses')
    expense_date    = models.DateField()
    description     = models.CharField(max_length=300)
    amount          = models.DecimalField(max_digits=15, decimal_places=2)
    payee           = models.CharField(max_length=200, blank=True)
    reference_no    = models.CharField(max_length=100, blank=True)
    notes           = models.TextField(blank=True)
    recorded_by     = models.ForeignKey(
        'accounts.User', null=True, on_delete=models.SET_NULL, related_name='expenses_recorded'
    )
    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PV-{self.voucher_number} | {self.description} | {self.amount}"

    def save(self, *args, **kwargs):
        if not self.voucher_number:
            self.voucher_number = self._generate_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_number():
        import time
        return 'E' + str(int(time.time() * 1000000))[-9:]

    class Meta:
        ordering = ['-expense_date', '-created_at']
