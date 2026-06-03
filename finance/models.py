from django.db import models
from django.db.models import Sum
from decimal import Decimal
from buildings.models import Building
from tenants.models import Tenant


class LedgerEntry(models.Model):
    ENTRY_CHARGE   = 'charge'
    ENTRY_PAYMENT  = 'payment'
    ENTRY_OPENING  = 'opening'
    ENTRY_ADJUSTMENT = 'adjustment'
    ENTRY_TYPES = [
        (ENTRY_CHARGE,     'Charge'),
        (ENTRY_PAYMENT,    'Payment'),
        (ENTRY_OPENING,    'Opening Balance'),
        (ENTRY_ADJUSTMENT, 'Adjustment'),
    ]

    tenant          = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ledger_entries')
    building        = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='ledger_entries')
    entry_date      = models.DateField()
    description     = models.CharField(max_length=300)
    entry_type      = models.CharField(max_length=20, choices=ENTRY_TYPES)
    debit_amount    = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    credit_amount   = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    running_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    reference       = models.CharField(max_length=100, blank=True)
    created_by      = models.ForeignKey(
        'accounts.User', null=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at      = models.DateTimeField(auto_now_add=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.entry_date} | {self.tenant} | Dr:{self.debit_amount} Cr:{self.credit_amount}"

    class Meta:
        ordering = ['entry_date', 'created_at']


class CashbookEntry(models.Model):
    SOURCE_RECEIPT = 'receipt'
    SOURCE_EXPENSE = 'expense'
    SOURCE_CHOICES = [(SOURCE_RECEIPT, 'Receipt'), (SOURCE_EXPENSE, 'Expense')]

    organisation    = models.ForeignKey('accounts.Organisation', on_delete=models.CASCADE, related_name='cashbook_entries')
    building        = models.ForeignKey(Building, null=True, blank=True, on_delete=models.SET_NULL, related_name='cashbook_entries')
    entry_date      = models.DateField()
    description     = models.CharField(max_length=300)
    source_type     = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_id       = models.PositiveIntegerField()
    debit           = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    credit          = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    balance         = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    created_at      = models.DateTimeField(auto_now_add=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.entry_date} | {self.description} | {self.debit or self.credit}"

    class Meta:
        ordering = ['entry_date', 'created_at']

    @classmethod
    def recompute_balance(cls, organisation):
        """Recompute running balance for all entries in order."""
        balance = Decimal('0')
        for entry in cls.objects.filter(organisation=organisation).order_by('entry_date', 'created_at'):
            balance += entry.debit - entry.credit
            entry.balance = balance
            entry.save(update_fields=['balance'])
