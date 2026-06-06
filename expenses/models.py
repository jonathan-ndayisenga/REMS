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


class Supplier(models.Model):
    """Creditor — every entity that takes money out of the business."""
    organisation = models.ForeignKey('accounts.Organisation', on_delete=models.CASCADE, related_name='suppliers')
    name         = models.CharField(max_length=200)
    phone        = models.CharField(max_length=30, blank=True)
    email        = models.EmailField(blank=True)
    address      = models.TextField(blank=True)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def total_invoiced(self):
        return self.expenses.aggregate(t=models.Sum('amount'))['t'] or Decimal('0')

    @property
    def total_paid(self):
        return self.expenses.aggregate(t=models.Sum('paid_amount'))['t'] or Decimal('0')

    @property
    def balance_outstanding(self):
        return self.total_invoiced - self.total_paid

    class Meta:
        ordering = ['name']


class Expense(models.Model):
    STATUS_UNPAID  = 'unpaid'
    STATUS_PARTIAL = 'partial'
    STATUS_PAID    = 'paid'
    PAYMENT_STATUS = [
        (STATUS_UNPAID,  'Unpaid'),
        (STATUS_PARTIAL, 'Partially Paid'),
        (STATUS_PAID,    'Paid'),
    ]

    voucher_number  = models.CharField(max_length=30, unique=True, editable=False)
    building        = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='expenses')
    category        = models.ForeignKey(ExpenseCategory, null=True, on_delete=models.SET_NULL, related_name='expenses')
    # Creditor link — if supplier is known, use FK; otherwise plain text payee
    supplier        = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.SET_NULL, related_name='expenses')
    payee           = models.CharField(max_length=200, blank=True, help_text='Name if supplier not in system')
    expense_date    = models.DateField()
    description     = models.CharField(max_length=300)
    amount          = models.DecimalField(max_digits=15, decimal_places=2, help_text='Total invoice amount')
    paid_amount     = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'),
                                         help_text='Amount actually paid so far')
    payment_status  = models.CharField(max_length=10, choices=PAYMENT_STATUS, default=STATUS_UNPAID)
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
        # Auto-set payment status from paid_amount
        if self.paid_amount >= self.amount:
            self.payment_status = self.STATUS_PAID
        elif self.paid_amount > 0:
            self.payment_status = self.STATUS_PARTIAL
        else:
            self.payment_status = self.STATUS_UNPAID
        super().save(*args, **kwargs)

    @property
    def balance_due(self):
        return self.amount - self.paid_amount

    @staticmethod
    def _generate_number():
        import time
        return 'E' + str(int(time.time() * 1000000))[-9:]

    class Meta:
        ordering = ['-expense_date', '-created_at']
