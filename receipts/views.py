from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseForbidden, HttpResponse
from django.utils import timezone
from decimal import Decimal
import io
from .models import Receipt
from .forms import ReceiptForm
from finance.models import LedgerEntry, CashbookEntry
from taxes.models import TaxSetting


@login_required
def receipt_list(request):
    if not request.user.can_receipt():
        return HttpResponseForbidden()
    buildings = request.user.get_buildings_qs()
    receipts = Receipt.objects.filter(building__in=buildings).select_related('tenant', 'building', 'cashier')
    building_filter = request.GET.get('building')
    if building_filter:
        receipts = receipts.filter(building_id=building_filter)
    return render(request, 'receipts/receipt_list.html', {'receipts': receipts, 'buildings': buildings, 'building_filter': building_filter})


@login_required
def receipt_create(request):
    if not request.user.can_receipt():
        return HttpResponseForbidden()
    form = ReceiptForm(request.POST or None, user=request.user)
    active_taxes = TaxSetting.objects.filter(
        organisation=request.user.organisation,
        is_active=True,
        tax_type=TaxSetting.TYPE_RECEIPT,
    )
    if request.method == 'POST' and form.is_valid():
        receipt = form.save(commit=False)
        receipt.cashier = request.user
        receipt.building = receipt.tenant.building

        # Calculate taxes
        gross = receipt.gross_amount
        tax_total = Decimal('0')
        breakdown = {}
        for tax in active_taxes:
            amount = (gross * tax.percentage / 100).quantize(Decimal('0.01'))
            tax_total += amount
            breakdown[tax.name] = str(amount)

        receipt.tax_deducted = tax_total
        receipt.net_amount   = gross - tax_total
        receipt.tax_breakdown = breakdown
        receipt.save()

        # Capture client IP for audit trail
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
             or request.META.get('REMOTE_ADDR')

        # Post to Ledger — with gross/tax/net particulars
        prev_balance = receipt.tenant.get_balance()
        LedgerEntry.objects.create(
            tenant=receipt.tenant,
            building=receipt.building,
            account_type=LedgerEntry.ACCT_DEBTOR,
            entry_date=receipt.receipt_date,
            period_month=receipt.period_month,
            period_year=receipt.period_year,
            description=f'Payment received — {receipt.get_payment_method_display()} (RCP-{receipt.receipt_number})',
            entry_type=LedgerEntry.ENTRY_PAYMENT,
            debit_amount=Decimal('0'),
            credit_amount=receipt.net_amount,
            gross_amount=receipt.gross_amount,
            tax_amount=receipt.tax_deducted,
            net_amount=receipt.net_amount,
            running_balance=prev_balance - receipt.net_amount,
            reference=receipt.receipt_number,
            created_by=request.user,
            ip_address=ip,
        )

        # Update MonthlyAccrual if one exists for this period
        from finance.models import MonthlyAccrual
        try:
            accrual = MonthlyAccrual.objects.get(
                tenant=receipt.tenant,
                period_month=receipt.period_month,
                period_year=receipt.period_year,
            )
            accrual.apply_payment(receipt.net_amount)
        except MonthlyAccrual.DoesNotExist:
            pass

        # Post to Cashbook
        last_cb = CashbookEntry.objects.filter(organisation=request.user.organisation).last()
        prev_cb_bal = last_cb.balance if last_cb else Decimal('0')
        CashbookEntry.objects.create(
            organisation=request.user.organisation,
            building=receipt.building,
            entry_date=receipt.receipt_date,
            description=f'Rent — {receipt.tenant.full_name} Rm {receipt.tenant.room_number} (RCP-{receipt.receipt_number})',
            source_type=CashbookEntry.SOURCE_RECEIPT,
            source_id=receipt.pk,
            debit=receipt.net_amount,
            credit=Decimal('0'),
            balance=prev_cb_bal + receipt.net_amount,
            ip_address=ip,
        )

        messages.success(request, f'Receipt RCP-{receipt.receipt_number} created.')
        return redirect('receipts:detail', pk=receipt.pk)
    return render(request, 'receipts/receipt_form.html', {'form': form, 'taxes': active_taxes, 'title': 'Issue Receipt'})


@login_required
def receipt_detail(request, pk):
    buildings = request.user.get_buildings_qs()
    receipt = get_object_or_404(Receipt, pk=pk, building__in=buildings)
    return render(request, 'receipts/receipt_detail.html', {'receipt': receipt})


@login_required
def receipt_pdf(request, pk):
    """Generate a PDF receipt using reportlab."""
    buildings = request.user.get_buildings_qs()
    receipt = get_object_or_404(Receipt, pk=pk, building__in=buildings)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    except ImportError:
        return HttpResponse('reportlab is not installed.', status=500)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )

    styles = getSampleStyleSheet()
    navy   = colors.HexColor('#0B1929')
    gold   = colors.HexColor('#C9A84C')
    grey   = colors.HexColor('#64748B')

    h1 = ParagraphStyle('h1', parent=styles['Normal'], fontSize=20, textColor=navy,
                        fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=4)
    sub = ParagraphStyle('sub', parent=styles['Normal'], fontSize=10, textColor=grey,
                         alignment=TA_CENTER, spaceAfter=2)
    rcpno = ParagraphStyle('rcpno', parent=styles['Normal'], fontSize=18, textColor=gold,
                           fontName='Helvetica-Bold', alignment=TA_CENTER, spaceAfter=12)
    label_s = ParagraphStyle('label', parent=styles['Normal'], fontSize=9, textColor=grey,
                              fontName='Helvetica-Bold')
    value_s = ParagraphStyle('value', parent=styles['Normal'], fontSize=10, textColor=navy,
                              fontName='Helvetica-Bold')
    footer_s = ParagraphStyle('footer', parent=styles['Normal'], fontSize=8, textColor=grey,
                               alignment=TA_CENTER)

    org = receipt.building.organisation

    story = [
        Paragraph('OFFICIAL RENT RECEIPT', h1),
        Paragraph(org.name, ParagraphStyle('orgname', parent=h1, fontSize=14)),
        Paragraph(receipt.building.name, sub),
        Spacer(1, 4*mm),
        Paragraph(f'RCP-{receipt.receipt_number}', rcpno),
        HRFlowable(width='100%', thickness=1, color=gold, spaceAfter=8),
    ]

    # Detail rows
    detail_data = [
        ['Date', receipt.receipt_date.strftime('%d %B %Y')],
        ['Tenant', receipt.tenant.full_name],
        ['Room', f'{receipt.tenant.room_number} — {receipt.building.name}'],
        ['Period', f'{receipt.period_month}/{receipt.period_year}'],
        ['Payment Method', receipt.get_payment_method_display()],
    ]
    if receipt.reference_no:
        detail_data.append(['Reference', receipt.reference_no])

    detail_table = Table(detail_data, colWidths=[50*mm, 110*mm])
    detail_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), grey),
        ('TEXTCOLOR', (1, 0), (1, -1), navy),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=6))

    # Amount breakdown
    amount_data = [
        ['Gross Amount', f'UGX {receipt.gross_amount:,.0f}'],
    ]
    for tax_name, amount in receipt.tax_breakdown.items():
        amount_data.append([f'{tax_name} (deducted)', f'- UGX {float(amount):,.0f}'])
    amount_data.append(['NET AMOUNT RECEIVED', f'UGX {receipt.net_amount:,.0f}'])

    amount_table = Table(amount_data, colWidths=[110*mm, 50*mm])
    amount_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (-1, -2), navy),
        ('TEXTCOLOR', (0, -1), (-1, -1), navy),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, gold),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FEF9EE')),
    ]))
    story.append(amount_table)
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceAfter=6))

    cashier_name = receipt.cashier.get_full_name() or receipt.cashier.username
    story.append(Paragraph(
        f'Issued by {cashier_name} &nbsp;·&nbsp; {receipt.created_at.strftime("%d %b %Y %H:%M")}',
        footer_s,
    ))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="receipt-RCP-{receipt.receipt_number}.pdf"'
    return response
