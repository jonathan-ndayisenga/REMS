from django.db import models
from django.db.models import Sum
from decimal import Decimal
from buildings.models import Building
from tenants.models import Tenant


class LedgerEntry(models.Model):
    """
    Double-entry ledger row.

    Account types and their normal balance side (which side INCREASES the account):
      DEBTOR   (Tenant)   — DR normal: charges increase DR, payments increase CR
      CREDITOR (Supplier) — CR normal: invoices increase CR, payments increase DR
      REVENUE             — CR normal: income increases CR
      EXPENSE             — DR normal: costs increase DR

    The seesaw (every entry has two sides):
      Rent charge posted:  DR Tenant Ledger  ↔  CR Revenue (Rent Earned)
      Payment received:    DR Cash (Cashbook) ↔  CR Tenant Ledger
      Expense invoiced:    DR Expense         ↔  CR Supplier Ledger
      Expense paid:        DR Supplier Ledger ↔  CR Cash (Cashbook)
    """
    # Account type — determines which side is the normal (increasing) balance
    ACCT_DEBTOR   = 'debtor'    # Tenant — asset/receivable
    ACCT_CREDITOR = 'creditor'  # Supplier — liability/payable
    ACCT_REVENUE  = 'revenue'   # Rent Earned
    ACCT_EXPENSE  = 'expense'   # Operating cost
    ACCT_TYPES = [
        (ACCT_DEBTOR,   'Debtor (Tenant)'),
        (ACCT_CREDITOR, 'Creditor (Supplier)'),
        (ACCT_REVENUE,  'Revenue'),
        (ACCT_EXPENSE,  'Expense'),
    ]

    # Entry types
    ENTRY_CHARGE     = 'charge'      # Monthly rent charge (DR Tenant)
    ENTRY_PAYMENT    = 'payment'     # Cash received / paid
    ENTRY_OPENING    = 'opening'     # Opening balance at registration
    ENTRY_ADJUSTMENT = 'adjustment'  # Manual correction
    ENTRY_ACCRUAL    = 'accrual'     # Accrued but not yet received/paid
    ENTRY_REVERSAL   = 'reversal'    # Reversal / credit note
    ENTRY_TYPES = [
        (ENTRY_CHARGE,     'Rent Charge'),
        (ENTRY_PAYMENT,    'Payment'),
        (ENTRY_OPENING,    'Opening Balance'),
        (ENTRY_ADJUSTMENT, 'Adjustment'),
        (ENTRY_ACCRUAL,    'Accrual'),
        (ENTRY_REVERSAL,   'Reversal'),
    ]

    # Account link — exactly one of tenant or supplier will be set
    tenant       = models.ForeignKey(Tenant, null=True, blank=True,
                                     on_delete=models.CASCADE, related_name='ledger_entries')
    supplier     = models.ForeignKey('expenses.Supplier', null=True, blank=True,
                                     on_delete=models.CASCADE, related_name='ledger_entries')
    building     = models.ForeignKey(Building, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='ledger_entries')
    account_type = models.CharField(max_length=10, choices=ACCT_TYPES, default=ACCT_DEBTOR)

    # Timing
    entry_date   = models.DateField()
    period_month = models.PositiveSmallIntegerField(null=True, blank=True)
    period_year  = models.PositiveSmallIntegerField(null=True, blank=True)

    # Particulars — what this entry represents
    description  = models.CharField(max_length=300)
    entry_type   = models.CharField(max_length=15, choices=ENTRY_TYPES)

    # Amounts — LEFT side (Debit) and RIGHT side (Credit)
    debit_amount  = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))

    # Breakdown (used when entry relates to a receipt with tax)
    gross_amount  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    tax_amount    = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    net_amount    = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    running_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    reference       = models.CharField(max_length=100, blank=True)

    # Audit
    created_by  = models.ForeignKey('accounts.User', null=True, on_delete=models.SET_NULL, related_name='+')
    created_at  = models.DateTimeField(auto_now_add=True)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        who = self.tenant or self.supplier or '—'
        return f"{self.entry_date} | {who} | Dr:{self.debit_amount} Cr:{self.credit_amount}"

    @property
    def balance_label(self):
        """Returns e.g. '800,000 Dr' or '0 Settled'."""
        bal = self.running_balance
        if bal > 0:
            return f"{bal:,.0f} Dr"
        elif bal < 0:
            return f"{abs(bal):,.0f} Cr"
        return "Settled"

    class Meta:
        ordering = ['entry_date', 'created_at']


class MonthlyAccrual(models.Model):
    """
    Tracks expected vs received rent per tenant per month.
    Created when monthly charges are posted; updated when receipts come in.
    """
    STATUS_UNPAID  = 'unpaid'
    STATUS_PARTIAL = 'partial'
    STATUS_SETTLED = 'settled'
    STATUS_CHOICES = [
        (STATUS_UNPAID,  'Unpaid'),
        (STATUS_PARTIAL, 'Partial'),
        (STATUS_SETTLED, 'Settled'),
    ]

    tenant           = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='monthly_accruals')
    period_month     = models.PositiveSmallIntegerField()
    period_year      = models.PositiveSmallIntegerField()
    expected_amount  = models.DecimalField(max_digits=15, decimal_places=2)
    received_amount  = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    status           = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_UNPAID)
    charge_entry     = models.ForeignKey(LedgerEntry, null=True, on_delete=models.SET_NULL, related_name='+')
    created_at       = models.DateTimeField(auto_now_add=True)

    @property
    def outstanding(self):
        return max(self.expected_amount - self.received_amount, Decimal('0'))

    def apply_payment(self, amount):
        """Apply a payment to this accrual and update status."""
        self.received_amount = min(self.received_amount + amount, self.expected_amount)
        if self.received_amount >= self.expected_amount:
            self.status = self.STATUS_SETTLED
        elif self.received_amount > 0:
            self.status = self.STATUS_PARTIAL
        self.save(update_fields=['received_amount', 'status'])

    def __str__(self):
        return f"{self.tenant} — {self.period_month}/{self.period_year} — {self.status}"

    class Meta:
        unique_together = [['tenant', 'period_month', 'period_year']]
        ordering = ['-period_year', '-period_month']


class CashbookEntry(models.Model):
    """
    Cash / Bank account — the asset that seesaws against every transaction.
    DR (left)  = money coming in  (receipts)
    CR (right) = money going out  (expenses paid)
    """
    SOURCE_RECEIPT = 'receipt'
    SOURCE_EXPENSE = 'expense'
    SOURCE_CHOICES = [(SOURCE_RECEIPT, 'Receipt'), (SOURCE_EXPENSE, 'Expense')]

    organisation = models.ForeignKey('accounts.Organisation', on_delete=models.CASCADE,
                                     related_name='cashbook_entries')
    building     = models.ForeignKey(Building, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='cashbook_entries')
    entry_date   = models.DateField()
    description  = models.CharField(max_length=300)
    source_type  = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_id    = models.PositiveIntegerField()
    debit        = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    credit       = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    balance      = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0'))
    created_at   = models.DateTimeField(auto_now_add=True)
    ip_address   = models.GenericIPAddressField(null=True, blank=True)

    def __str__(self):
        return f"{self.entry_date} | {self.description} | {self.debit or self.credit}"

    class Meta:
        ordering = ['entry_date', 'created_at']

    @classmethod
    def recompute_balance(cls, organisation):
        balance = Decimal('0')
        for entry in cls.objects.filter(organisation=organisation).order_by('entry_date', 'created_at'):
            balance += entry.debit - entry.credit
            entry.balance = balance
            entry.save(update_fields=['balance'])
