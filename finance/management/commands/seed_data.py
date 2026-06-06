"""
Management command: seed_data

Populates:
  • Suppliers    — 6 realistic Ugandan suppliers for Kampala Properties Ltd
  • Expenses     — 12 expenses spread across the last 6 months, linked to suppliers,
                   with a mix of paid / partial / unpaid statuses
  • Creditor ledger entries — auto-generated for each expense (invoice CR + payment DR)
  • Debtor ledger charges   — monthly rent charges for the last 3 months for all active
                              tenants (skip months that already have a charge)
  • MonthlyAccrual records  — one per tenant per charged month
  • Cashbook entries        — one per paid/partial expense

Usage:
  python manage.py seed_data
  python manage.py seed_data --clear   # wipe suppliers+seed expenses first
"""
import datetime
import time
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Organisation
from buildings.models import Building
from tenants.models import Tenant
from expenses.models import Supplier, Expense, ExpenseCategory
from finance.models import LedgerEntry, CashbookEntry, MonthlyAccrual


SUPPLIERS = [
    {
        'name':    'Nile Electricals & Contractors',
        'phone':   '+256 701 123 456',
        'email':   'info@nileelectrical.co.ug',
        'address': 'Plot 14, Kampala Industrial Area',
        'notes':   'Handles all electrical maintenance contracts.',
    },
    {
        'name':    'Greenfield Plumbing Works',
        'phone':   '+256 772 234 567',
        'email':   'greenfield@plumbing.ug',
        'address': 'Ntinda, Kampala',
        'notes':   'Preferred plumber for all three properties.',
    },
    {
        'name':    'Kampala Security Solutions',
        'phone':   '+256 752 345 678',
        'email':   'ops@kss.co.ug',
        'address': 'Nakasero, Kampala',
        'notes':   'Monthly security guard contract.',
    },
    {
        'name':    'Cleanpro Facilities Ltd',
        'phone':   '+256 702 456 789',
        'email':   'cleanpro@gmail.com',
        'address': 'Bugolobi, Kampala',
        'notes':   'Cleaning and waste management.',
    },
    {
        'name':    'Uganda Water & Sewerage Corp',
        'phone':   '+256 417 600 100',
        'email':   'billing@nwsc.co.ug',
        'address': 'Plot 39, Jinja Road, Kampala',
        'notes':   'Utility — quarterly water bills.',
    },
    {
        'name':    'Stanbic Paint & Hardware',
        'phone':   '+256 783 567 890',
        'email':   'sales@stanbichardware.ug',
        'address': 'Owino Market, Kampala',
        'notes':   'Paint, tiles and general building materials.',
    },
]


class Command(BaseCommand):
    help = 'Seed suppliers, expenses, creditor ledger entries and monthly rent charges.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete all existing suppliers and seed-generated expenses before seeding.'
        )

    @transaction.atomic
    def handle(self, **options):
        try:
            org = Organisation.objects.get(name='Kampala Properties Ltd')
        except Organisation.DoesNotExist:
            org = Organisation.objects.first()
            if not org:
                self.stdout.write(self.style.ERROR('No organisation found. Create one first.'))
                return

        buildings = list(Building.objects.filter(organisation=org))
        if not buildings:
            self.stdout.write(self.style.ERROR('No buildings found for this organisation.'))
            return

        if options['clear']:
            deleted_s, _ = Supplier.objects.filter(organisation=org).delete()
            self.stdout.write(f'  Cleared {deleted_s} suppliers.')

        # ── 1. Suppliers ────────────────────────────────────────────────────────
        self.stdout.write('Creating suppliers...')
        supplier_objs = {}
        for data in SUPPLIERS:
            s, created = Supplier.objects.get_or_create(
                organisation=org,
                name=data['name'],
                defaults={k: v for k, v in data.items() if k != 'name'},
            )
            supplier_objs[s.name] = s
            self.stdout.write(f'  {"+" if created else "~"} {s.name}')

        # ── 2. Expense category (Maintenance) ────────────────────────────────
        cat_maintenance, _ = ExpenseCategory.objects.get_or_create(organisation=org, name='Maintenance')
        cat_security,    _ = ExpenseCategory.objects.get_or_create(organisation=org, name='Security')
        cat_utilities,   _ = ExpenseCategory.objects.get_or_create(organisation=org, name='Utilities')
        cat_cleaning,    _ = ExpenseCategory.objects.get_or_create(organisation=org, name='Cleaning')

        today = datetime.date.today()

        def months_ago(n):
            m = today.month - n
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            return datetime.date(y, m, 1)

        # ── 3. Expenses ──────────────────────────────────────────────────────
        # (supplier_name, building_index, category, description, amount, paid_amount, date_offset_months)
        EXPENSE_DATA = [
            ('Nile Electricals & Contractors',  0, cat_maintenance, 'Rewiring stairwell lights — Ntinda Heights',    1_800_000, 1_800_000, 5),
            ('Nile Electricals & Contractors',  1, cat_maintenance, 'Generator servicing — Nakawa Court',             950_000,   500_000, 3),
            ('Greenfield Plumbing Works',       0, cat_maintenance, 'Water pump replacement — Ntinda Heights',       1_200_000, 1_200_000, 4),
            ('Greenfield Plumbing Works',       2, cat_maintenance, 'Blocked drains clearance — Bugolobi Flats',       350_000,   350_000, 2),
            ('Greenfield Plumbing Works',       1, cat_maintenance, 'Roof gutter repair — Nakawa Court',               600_000,         0, 1),
            ('Kampala Security Solutions',      0, cat_security,    'Monthly security contract — Ntinda Heights',      900_000,   900_000, 5),
            ('Kampala Security Solutions',      0, cat_security,    'Monthly security contract — Ntinda Heights',      900_000,   900_000, 4),
            ('Kampala Security Solutions',      0, cat_security,    'Monthly security contract — Ntinda Heights',      900_000,   900_000, 3),
            ('Kampala Security Solutions',      0, cat_security,    'Monthly security contract — Ntinda Heights',      900_000,   450_000, 2),
            ('Cleanpro Facilities Ltd',         2, cat_cleaning,    'Monthly cleaning — Bugolobi Flats',               480_000,   480_000, 3),
            ('Uganda Water & Sewerage Corp',    1, cat_utilities,   'Quarterly water bill — Nakawa Court',             275_000,   275_000, 4),
            ('Stanbic Paint & Hardware',        0, cat_maintenance, 'Paint & materials — façade repaint, Ntinda',    2_500_000, 1_000_000, 2),
        ]

        self.stdout.write('Creating expenses and ledger entries...')
        for (sup_name, b_idx, category, description, amount, paid, months_back) in EXPENSE_DATA:
            supplier  = supplier_objs[sup_name]
            building  = buildings[b_idx % len(buildings)]
            exp_date  = months_ago(months_back)
            amount    = Decimal(str(amount))
            paid      = Decimal(str(paid))

            # Skip if identical expense already exists
            if Expense.objects.filter(building=building, description=description, expense_date=exp_date).exists():
                self.stdout.write(f'  ~ skipping (exists): {description[:50]}')
                continue

            expense = Expense(
                building=building,
                category=category,
                supplier=supplier,
                expense_date=exp_date,
                description=description,
                amount=amount,
                paid_amount=paid,
                recorded_by=None,
            )
            time.sleep(0.002)  # ensure unique microsecond-based voucher_number
            expense.save()

            # Cashbook: cash out for paid portion
            if paid > 0:
                last_cb = CashbookEntry.objects.filter(organisation=org).order_by('entry_date', 'created_at').last()
                prev_bal = last_cb.balance if last_cb else Decimal('0')
                CashbookEntry.objects.create(
                    organisation=org,
                    building=building,
                    entry_date=exp_date,
                    description=f'{description} (PV-{expense.voucher_number})',
                    source_type=CashbookEntry.SOURCE_EXPENSE,
                    source_id=expense.pk,
                    debit=Decimal('0'),
                    credit=paid,
                    balance=prev_bal - paid,
                )

            # Creditor ledger: CR invoice, DR payment
            prev_entries = supplier.ledger_entries.order_by('-created_at').first()
            prev_bal_sup = prev_entries.running_balance if prev_entries else Decimal('0')
            inv_balance  = prev_bal_sup + amount

            LedgerEntry.objects.create(
                supplier=supplier,
                building=building,
                account_type=LedgerEntry.ACCT_CREDITOR,
                entry_date=exp_date,
                period_month=exp_date.month,
                period_year=exp_date.year,
                description=f'Invoice — {description} (PV-{expense.voucher_number})',
                entry_type=LedgerEntry.ENTRY_OPENING,
                debit_amount=Decimal('0'),
                credit_amount=amount,
                running_balance=inv_balance,
                reference=expense.voucher_number,
            )

            if paid > 0:
                LedgerEntry.objects.create(
                    supplier=supplier,
                    building=building,
                    account_type=LedgerEntry.ACCT_CREDITOR,
                    entry_date=exp_date,
                    period_month=exp_date.month,
                    period_year=exp_date.year,
                    description=f'Payment — {description} (PV-{expense.voucher_number})',
                    entry_type=LedgerEntry.ENTRY_PAYMENT,
                    debit_amount=paid,
                    credit_amount=Decimal('0'),
                    running_balance=inv_balance - paid,
                    reference=expense.voucher_number,
                )

            self.stdout.write(f'  + PV-{expense.voucher_number} | {sup_name[:28]:28} | {description[:40]}')

        # ── 4. Monthly rent charges — last 3 months ─────────────────────────
        self.stdout.write('Posting monthly rent charges (last 3 months)...')
        tenants = list(Tenant.objects.filter(building__in=buildings, status='active').select_related('building'))

        for months_back in (3, 2, 1):
            charge_date = months_ago(months_back)
            month = charge_date.month
            year  = charge_date.year

            for tenant in tenants:
                if MonthlyAccrual.objects.filter(tenant=tenant, period_month=month, period_year=year).exists():
                    continue

                rate = tenant.monthly_rate or (tenant.building.standard_rate or Decimal('0'))
                if rate <= 0:
                    continue

                # Running balance on the debtor account
                prev = tenant.ledger_entries.filter(
                    account_type=LedgerEntry.ACCT_DEBTOR
                ).order_by('-created_at').first()
                prev_bal = prev.running_balance if prev else Decimal('0')

                entry = LedgerEntry.objects.create(
                    tenant=tenant,
                    building=tenant.building,
                    account_type=LedgerEntry.ACCT_DEBTOR,
                    entry_date=charge_date,
                    period_month=month,
                    period_year=year,
                    description=f'Monthly rent charge — {charge_date.strftime("%B %Y")}',
                    entry_type=LedgerEntry.ENTRY_CHARGE,
                    debit_amount=rate,
                    credit_amount=Decimal('0'),
                    running_balance=prev_bal + rate,
                )
                MonthlyAccrual.objects.create(
                    tenant=tenant,
                    period_month=month,
                    period_year=year,
                    expected_amount=rate,
                    charge_entry=entry,
                )

            self.stdout.write(f'  + Charges posted for {charge_date.strftime("%B %Y")}')

        # ── 5. Simulate some payments against the accruals (partial realism) ──
        self.stdout.write('Simulating partial rent payments against accruals...')
        # Pay off month -3 fully, month -2 partially for some tenants
        for tenant in tenants[:6]:
            for months_back, pay_fraction in ((3, Decimal('1')), (2, Decimal('0.5'))):
                charge_date = months_ago(months_back)
                try:
                    accrual = MonthlyAccrual.objects.get(
                        tenant=tenant,
                        period_month=charge_date.month,
                        period_year=charge_date.year,
                    )
                except MonthlyAccrual.DoesNotExist:
                    continue

                if accrual.status == MonthlyAccrual.STATUS_SETTLED:
                    continue

                pay_amount = (accrual.expected_amount * pay_fraction).quantize(Decimal('1'))

                # Credit the debtor ledger
                prev = tenant.ledger_entries.filter(
                    account_type=LedgerEntry.ACCT_DEBTOR
                ).order_by('-created_at').first()
                prev_bal = prev.running_balance if prev else Decimal('0')

                LedgerEntry.objects.create(
                    tenant=tenant,
                    building=tenant.building,
                    account_type=LedgerEntry.ACCT_DEBTOR,
                    entry_date=charge_date + datetime.timedelta(days=5),
                    period_month=charge_date.month,
                    period_year=charge_date.year,
                    description=f'Rent payment — {charge_date.strftime("%B %Y")} (seed)',
                    entry_type=LedgerEntry.ENTRY_PAYMENT,
                    debit_amount=Decimal('0'),
                    credit_amount=pay_amount,
                    gross_amount=pay_amount,
                    tax_amount=Decimal('0'),
                    net_amount=pay_amount,
                    running_balance=prev_bal - pay_amount,
                )
                accrual.apply_payment(pay_amount)

                # Cashbook debit (cash in)
                last_cb = CashbookEntry.objects.filter(organisation=org).order_by('entry_date', 'created_at').last()
                prev_cb = last_cb.balance if last_cb else Decimal('0')
                CashbookEntry.objects.create(
                    organisation=org,
                    building=tenant.building,
                    entry_date=charge_date + datetime.timedelta(days=5),
                    description=f'Rent — {tenant.full_name} Rm {tenant.room_number} ({charge_date.strftime("%b %Y")}) seed',
                    source_type=CashbookEntry.SOURCE_RECEIPT,
                    source_id=0,
                    debit=pay_amount,
                    credit=Decimal('0'),
                    balance=prev_cb + pay_amount,
                )

        self.stdout.write(self.style.SUCCESS('\nSeed complete.'))
        self.stdout.write(f'  Suppliers:       {Supplier.objects.filter(organisation=org).count()}')
        self.stdout.write(f'  Expenses:        {Expense.objects.filter(building__in=buildings).count()}')
        self.stdout.write(f'  LedgerEntries:   {LedgerEntry.objects.filter(building__in=buildings).count()}')
        self.stdout.write(f'  MonthlyAccruals: {MonthlyAccrual.objects.filter(tenant__building__in=buildings).count()}')
