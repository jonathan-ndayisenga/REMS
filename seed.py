"""Seed script — creates demo data for REMS.

Safe to run multiple times: wipes previous seed data first.
"""
import os, django, datetime, random
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from decimal import Decimal
from accounts.models import Organisation, User, UserRole
from buildings.models import Building
from tenants.models import Tenant
from taxes.models import TaxSetting
from finance.models import LedgerEntry, CashbookEntry
from receipts.models import Receipt
from expenses.models import Expense, ExpenseCategory

# ── Wipe previous seed data ──────────────────────────────────────────────────
print("Clearing previous seed data...")
Organisation.objects.filter(name="Kampala Properties Ltd").delete()
for uname in ('admin', 'accountant', 'cashier_r', 'cashier_e', 'propman'):
    User.objects.filter(username=uname).delete()

# ── Organisation ─────────────────────────────────────────────────────────────
org = Organisation.objects.create(
    name="Kampala Properties Ltd",
    contact_email="admin@kpl.co.ug",
    phone="+256 700 123456",
    address="Plot 5, Kampala Road, Kampala, Uganda",
    subscription_status="active",
)

# ── Users ────────────────────────────────────────────────────────────────────
op = User.objects.create_user(
    'admin', 'admin@kpl.co.ug', 'admin123',
    first_name='Jonathan', last_name='Mugisha',
    role=User.ROLE_OP_MANAGER, organisation=org,
)
accountant = User.objects.create_user(
    'accountant', 'acc@kpl.co.ug', 'admin123',
    first_name='Sarah', last_name='Nakato',
    role=User.ROLE_ACCOUNTANT, organisation=org,
)
cashier_r = User.objects.create_user(
    'cashier_r', 'cr@kpl.co.ug', 'admin123',
    first_name='Moses', last_name='Okello',
    role=User.ROLE_CASHIER_RECEIPTS, organisation=org,
)
cashier_e = User.objects.create_user(
    'cashier_e', 'ce@kpl.co.ug', 'admin123',
    first_name='Grace', last_name='Atim',
    role=User.ROLE_CASHIER_EXPENSES, organisation=org,
)
prop_mgr = User.objects.create_user(
    'propman', 'pm@kpl.co.ug', 'admin123',
    first_name='David', last_name='Ssekandi',
    role=User.ROLE_PROPERTY_MANAGER, organisation=org,
)

# Demo: cashier_r also has Cashier-Expenses role (multi-role)
UserRole.objects.create(user=cashier_r, role=User.ROLE_CASHIER_EXPENSES)

# ── Buildings ────────────────────────────────────────────────────────────────
b1 = Building.objects.create(
    organisation=org, name="Ntinda Heights",
    address="Plot 14, Ntinda Road, Kampala", total_rooms=20,
)
b2 = Building.objects.create(
    organisation=org, name="Nakawa Court",
    address="Plot 7, Nakawa Industrial Area", total_rooms=15,
)
b3 = Building.objects.create(
    organisation=org, name="Bugolobi Flats",
    address="Plot 22, Luthuli Avenue, Bugolobi", total_rooms=10,
)

# ── Tax Settings ─────────────────────────────────────────────────────────────
# WHT is a transaction-level tax (deducted on each receipt)
tax_wht = TaxSetting.objects.create(
    organisation=org,
    name="Withholding Tax on Rent",
    description="Withheld by tenant payer and remitted to URA. Applies to company/govt tenants.",
    percentage=Decimal('6.0'),
    tax_type=TaxSetting.TYPE_RECEIPT,
    is_active=True,
    created_by=accountant,
)
# RIT is an income-level tax (applied at P&L stage only)
tax_rit = TaxSetting.objects.create(
    organisation=org,
    name="Rental Income Tax (RIT)",
    description="Flat tax on gross rental income for individual landlords above UGX 2.82M/year.",
    percentage=Decimal('12.0'),
    tax_type=TaxSetting.TYPE_INCOME,
    is_active=True,
    created_by=accountant,
)

# ── Expense Categories ───────────────────────────────────────────────────────
cat1 = ExpenseCategory.objects.create(organisation=org, name="Maintenance & Repairs")
cat2 = ExpenseCategory.objects.create(organisation=org, name="Utilities")
cat3 = ExpenseCategory.objects.create(organisation=org, name="Security")
cat4 = ExpenseCategory.objects.create(organisation=org, name="Administration")

# ── Tenants ──────────────────────────────────────────────────────────────────
tenant_data = [
    (b1, "Alice Namukasa",      "101", Decimal('800000')),
    (b1, "Robert Kiggundu",     "102", Decimal('750000')),
    (b1, "Fatuma Hassan",       "103", Decimal('900000')),
    (b1, "Peter Ssemwogerere",  "201", Decimal('1000000')),
    (b2, "Christine Amoding",   "A1",  Decimal('600000')),
    (b2, "John Muwanguzi",      "A2",  Decimal('650000')),
    (b2, "Mary Ochieng",        "B1",  Decimal('700000')),
    (b3, "Samuel Tukei",        "F1",  Decimal('550000')),
    (b3, "Judith Akello",       "F2",  Decimal('600000')),
]

tenants = []
for building, name, room, rate in tenant_data:
    t = Tenant.objects.create(
        building=building,
        full_name=name,
        room_number=room,
        monthly_rate=rate,
        lease_start=datetime.date(2024, 1, 1),
        status='active',
        registered_by=prop_mgr,
    )
    # Opening ledger entry per tenant
    LedgerEntry.objects.create(
        tenant=t, building=building,
        entry_date=datetime.date(2024, 1, 1),
        description='Opening balance — Tenant registration',
        entry_type=LedgerEntry.ENTRY_OPENING,
        debit_amount=rate,
        credit_amount=Decimal('0'),
        running_balance=rate,
        created_by=prop_mgr,
    )
    tenants.append(t)

# ── 12 months of historical receipts & expenses ──────────────────────────────
today = datetime.date.today()
cb_balance = Decimal('0')

random.seed(42)  # reproducible

for month_offset in range(11, -1, -1):
    d = today.replace(day=1) - datetime.timedelta(days=month_offset * 30)

    # Receipts — 85% payment rate per tenant
    for t in tenants:
        if random.random() < 0.85:
            gross = t.monthly_rate
            tax_amt = (gross * tax_wht.percentage / 100).quantize(Decimal('0.01'))
            net = gross - tax_amt
            receipt_day = random.randint(1, 5)
            try:
                receipt_date = d.replace(day=receipt_day)
            except ValueError:
                receipt_date = d.replace(day=1)

            r = Receipt.objects.create(
                tenant=t, building=t.building,
                receipt_date=receipt_date,
                period_month=d.month, period_year=d.year,
                gross_amount=gross,
                tax_deducted=tax_amt,
                net_amount=net,
                payment_method='cash',
                cashier=cashier_r,
                tax_breakdown={tax_wht.name: str(tax_amt)},
            )
            cb_balance += net
            CashbookEntry.objects.create(
                organisation=org, building=t.building,
                entry_date=r.receipt_date,
                description=f'Rent — {t.full_name} Rm {t.room_number} (RCP-{r.receipt_number})',
                source_type=CashbookEntry.SOURCE_RECEIPT,
                source_id=r.pk,
                debit=net, credit=Decimal('0'), balance=cb_balance,
            )
            # Track running balance per tenant ledger
            LedgerEntry.objects.create(
                tenant=t, building=t.building,
                entry_date=r.receipt_date,
                description=f'Payment received — Cash (RCP-{r.receipt_number})',
                entry_type=LedgerEntry.ENTRY_PAYMENT,
                debit_amount=Decimal('0'),
                credit_amount=net,
                running_balance=Decimal('0'),
                reference=r.receipt_number,
                created_by=cashier_r,
            )

    # Monthly expenses
    expense_items = [
        (b1, cat1, "Generator fuel & servicing",  Decimal('250000')),
        (b2, cat2, "NWSC Water Bill",              Decimal('180000')),
        (b3, cat3, "Security guard wages",         Decimal('350000')),
        (b1, cat4, "Office stationery",            Decimal('45000')),
    ]
    for building, category, desc, amount in expense_items:
        if random.random() < 0.8:
            try:
                exp_day = random.randint(10, 25)
                exp_date = d.replace(day=exp_day)
            except ValueError:
                exp_date = d.replace(day=10)

            exp = Expense.objects.create(
                building=building, category=category,
                expense_date=exp_date,
                description=desc,
                amount=amount,
                recorded_by=cashier_e,
            )
            cb_balance -= amount
            CashbookEntry.objects.create(
                organisation=org, building=building,
                entry_date=exp.expense_date,
                description=f'{desc} (PV-{exp.voucher_number})',
                source_type=CashbookEntry.SOURCE_EXPENSE,
                source_id=exp.pk,
                debit=Decimal('0'), credit=amount, balance=cb_balance,
            )

# ── Summary ──────────────────────────────────────────────────────────────────
print("\nSeed complete!")
print(f"   Organisation : {org.name}")
print(f"   Users        : admin / accountant / cashier_r / cashier_e / propman  (password: admin123)")
print(f"   Buildings    : {Building.objects.filter(organisation=org).count()}")
print(f"   Tenants      : {Tenant.objects.filter(building__organisation=org).count()}")
print(f"   Receipts     : {Receipt.objects.filter(building__organisation=org).count()}")
print(f"   Expenses     : {Expense.objects.filter(building__organisation=org).count()}")
print(f"   Cashbook     : {CashbookEntry.objects.filter(organisation=org).count()} entries")
print(f"   Cash balance : UGX {cb_balance:,.0f}")
