# REMS — Real Estate Management System
### Django Application

## Quick Start

```bash
# 1. Install dependencies
pip install django django-crispy-forms crispy-bootstrap5 Pillow reportlab

# 2. Apply migrations
python manage.py migrate

# 3. Seed demo data (optional)
python seed.py

# 4. Run the server
python manage.py runserver
```

## Demo Login Credentials

| Username     | Password  | Role                    |
|-------------|-----------|-------------------------|
| admin       | admin123  | Operational Manager     |
| accountant  | admin123  | Accountant              |
| cashier_r   | admin123  | Cashier – Receipts      |
| cashier_e   | admin123  | Cashier – Expenses      |
| propman     | admin123  | Property Manager        |

Visit: http://127.0.0.1:8000

## Project Structure

```
rems/
├── accounts/      User model, roles, authentication
├── buildings/     Building management
├── tenants/       Tenant registration, rent roll
├── receipts/      Cashier receipts module
├── expenses/      Cashier expenses & payment vouchers
├── finance/       Cashbook, Ledger, Trial Balance, P&L, Balance Sheet
├── taxes/         Tax settings (Accountant only)
├── dashboard/     Executive dashboard with charts
├── templates/     All HTML templates
│   └── base.html  Base layout with sidebar
├── static/
│   └── css/rems.css  Professional accounting UI styles
├── config/        Django settings & URLs
└── seed.py        Demo data generator
```

## Key Features
- **Role-based access**: 6 distinct roles, permission-enforced on every view
- **Tax automation**: Active taxes auto-deducted at receipting, itemised on receipts
- **Double-entry**: Every receipt/expense posts to both Cashbook and Ledger
- **Financial reports**: Cashbook, Ledger, Trial Balance, P&L, Balance Sheet
- **Dashboard**: 12-month revenue curve, building occupancy, aged receivables
- **Print-ready**: Receipts and payment vouchers are print-optimised
