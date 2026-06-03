from django.contrib.auth.models import AbstractUser
from django.db import models


class Organisation(models.Model):
    name = models.CharField(max_length=200)
    contact_email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    subscription_status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('suspended', 'Suspended'), ('trial', 'Trial')],
        default='trial'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class User(AbstractUser):
    ROLE_SUPER_ADMIN        = 'super_admin'
    ROLE_OP_MANAGER         = 'op_manager'
    ROLE_PROPERTY_MANAGER   = 'property_manager'
    ROLE_CASHIER_RECEIPTS   = 'cashier_receipts'
    ROLE_CASHIER_EXPENSES   = 'cashier_expenses'
    ROLE_ACCOUNTANT         = 'accountant'

    ROLE_CHOICES = [
        (ROLE_SUPER_ADMIN,      'Super Admin'),
        (ROLE_OP_MANAGER,       'Operational Manager'),
        (ROLE_PROPERTY_MANAGER, 'Property Manager'),
        (ROLE_CASHIER_RECEIPTS, 'Cashier – Receipts'),
        (ROLE_CASHIER_EXPENSES, 'Cashier – Expenses'),
        (ROLE_ACCOUNTANT,       'Accountant'),
    ]

    organisation = models.ForeignKey(
        Organisation, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='users'
    )
    # Primary role kept for display and backward compat; multi-role is via UserRole
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_CASHIER_RECEIPTS)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    # Building-level scoping (optional — if blank, user accesses all buildings in their org)
    buildings = models.ManyToManyField('buildings.Building', blank=True, related_name='assigned_users')

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    # ── multi-role helper ───────────────────────────────────────────────────
    def has_role(self, role_key):
        """True if user has this role as primary OR as an additional role."""
        if self.role == role_key:
            return True
        return self.user_roles.filter(role=role_key).exists()

    def all_roles(self):
        """Return list of all role keys this user holds."""
        roles = set([self.role])
        roles.update(self.user_roles.values_list('role', flat=True))
        return list(roles)

    def all_roles_display(self):
        """Human-readable list of all roles."""
        label = dict(self.ROLE_CHOICES)
        return [label.get(r, r) for r in self.all_roles()]

    # ── permission helpers ──────────────────────────────────────────────────
    @property
    def is_super_admin(self):
        return self.has_role(self.ROLE_SUPER_ADMIN)

    @property
    def is_op_manager(self):
        return self.has_role(self.ROLE_OP_MANAGER)

    @property
    def is_property_manager(self):
        return self.has_role(self.ROLE_PROPERTY_MANAGER)

    @property
    def is_cashier_receipts(self):
        return self.has_role(self.ROLE_CASHIER_RECEIPTS)

    @property
    def is_cashier_expenses(self):
        return self.has_role(self.ROLE_CASHIER_EXPENSES)

    @property
    def is_accountant(self):
        return self.has_role(self.ROLE_ACCOUNTANT)

    def can_access_finance(self):
        return self.is_op_manager or self.is_accountant

    def can_receipt(self):
        return self.is_op_manager or self.is_cashier_receipts

    def can_expense(self):
        return self.is_op_manager or self.is_cashier_expenses

    def can_manage_tenants(self):
        return self.is_op_manager or self.is_property_manager

    def can_configure_taxes(self):
        return self.is_accountant

    def can_delete(self):
        return self.is_super_admin or self.is_op_manager

    def get_buildings_qs(self):
        """Return QuerySet of buildings this user can access."""
        from buildings.models import Building
        if self.is_super_admin:
            return Building.objects.all()
        if self.is_op_manager:
            return Building.objects.filter(organisation=self.organisation)
        assigned = self.buildings.filter(organisation=self.organisation)
        if assigned.exists():
            return assigned
        return Building.objects.filter(organisation=self.organisation)


class UserRole(models.Model):
    """Additional roles for a user beyond their primary role (multi-role support)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.CharField(max_length=30, choices=User.ROLE_CHOICES)

    class Meta:
        unique_together = [('user', 'role')]
        ordering = ['role']

    def __str__(self):
        return f"{self.user} + {self.get_role_display()}"
