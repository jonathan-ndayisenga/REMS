"""
Management command: post_monthly_charges

Usage:
  python manage.py post_monthly_charges            # current month
  python manage.py post_monthly_charges --month 6 --year 2026
"""
import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from tenants.models import Tenant
from finance.models import LedgerEntry, MonthlyAccrual


class Command(BaseCommand):
    help = 'Post monthly rent charges for all active tenants.'

    def add_arguments(self, parser):
        today = datetime.date.today()
        parser.add_argument('--month', type=int, default=today.month)
        parser.add_argument('--year',  type=int, default=today.year)

    def handle(self, *args, **options):
        month = options['month']
        year  = options['year']
        charge_date = datetime.date(year, month, 1)

        tenants = Tenant.objects.filter(status='active').select_related('building')
        posted = skipped = 0

        for tenant in tenants:
            if MonthlyAccrual.objects.filter(tenant=tenant, period_month=month, period_year=year).exists():
                skipped += 1
                continue
            rate = tenant.monthly_rate or (tenant.building.standard_rate or Decimal('0'))
            if rate <= 0:
                skipped += 1
                continue

            prev_entries = tenant.ledger_entries.filter(
                account_type=LedgerEntry.ACCT_DEBTOR
            ).order_by('-created_at').first()
            prev_bal = prev_entries.running_balance if prev_entries else Decimal('0')

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
            posted += 1

        self.stdout.write(self.style.SUCCESS(
            f'Posted charges for {charge_date.strftime("%B %Y")}: {posted} tenants charged, {skipped} skipped.'
        ))
