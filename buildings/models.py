from django.db import models
from accounts.models import Organisation


class Building(models.Model):
    organisation  = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name='buildings')
    name          = models.CharField(max_length=200)
    address       = models.TextField(blank=True)
    total_rooms   = models.PositiveIntegerField(default=0)
    standard_rate = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        help_text='Default monthly rent per room for this building (UGX)'
    )
    description   = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.organisation.name})"

    @property
    def occupied_rooms(self):
        return self.tenants.filter(status='active').count()

    @property
    def vacant_rooms(self):
        return max(self.total_rooms - self.occupied_rooms, 0)

    @property
    def occupancy_rate(self):
        if self.total_rooms == 0:
            return 0
        return round((self.occupied_rooms / self.total_rooms) * 100, 1)

    class Meta:
        ordering = ['name']
