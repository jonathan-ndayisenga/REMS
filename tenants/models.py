from django.db import models
from django.utils import timezone
from buildings.models import Building


class Tenant(models.Model):
    STATUS_ACTIVE   = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES  = [(STATUS_ACTIVE, 'Active'), (STATUS_INACTIVE, 'Inactive')]

    building        = models.ForeignKey(Building, on_delete=models.CASCADE, related_name='tenants')
    full_name       = models.CharField(max_length=200)
    email           = models.EmailField(blank=True)
    phone           = models.CharField(max_length=30, blank=True)
    room_number     = models.CharField(max_length=20)
    monthly_rate    = models.DecimalField(max_digits=15, decimal_places=2)
    lease_start     = models.DateField(default=timezone.now)
    lease_end       = models.DateField(null=True, blank=True)
    security_deposit= models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    notes           = models.TextField(blank=True)
    registered_by   = models.ForeignKey(
        'accounts.User', null=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at      = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} — Room {self.room_number} ({self.building.name})"

    def get_balance(self):
        """Positive = tenant owes, Negative = tenant has credit."""
        from finance.models import LedgerEntry
        entries = LedgerEntry.objects.filter(tenant=self)
        total_debit  = sum(e.debit_amount  for e in entries)
        total_credit = sum(e.credit_amount for e in entries)
        return total_debit - total_credit

    def days_overdue(self):
        balance = self.get_balance()
        if balance <= 0:
            return 0
        today = timezone.now().date()
        diff = today - self.lease_start
        return max(diff.days, 0)

    class Meta:
        ordering = ['building', 'room_number']
        unique_together = [['building', 'room_number']]
