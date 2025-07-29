from django.db import models, transaction
import datetime
from django.utils.timezone import now
from django.utils import timezone
import json

class AuditModel(models.Model):
    created_by = models.CharField(max_length=100, blank=True, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, blank=True, null=True)
    lastmodified_date = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        abstract = True

class TravellersIN(AuditModel):
    # Basic Information
    purchase_category = models.CharField(max_length=50, choices=[
        ('TRAVELLERS IN CREDIT', 'TRAVELLERS IN CREDIT'),
        ('TRAVELLERS IN CASH', 'TRAVELLERS IN CASH'),
    ])
    vendor = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField()
    supplier_address = models.TextField(blank=True, null=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    invoice_no = models.CharField(max_length=100)
    invoice_date = models.DateField()
    credit_period = models.CharField(max_length=50, blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    reference = models.CharField(max_length=255, blank=True, null=True)
    payment_mode = models.CharField(max_length=20, choices=[
        ('CHEQUE', 'CHEQUE'),
        ('CASH', 'CASH'),
        ('CARD', 'CARD'),
        ('UPI', 'UPI'),
    ], blank=True, null=True)
    
    # Items stored as JSON
    items = models.JSONField(default=list, blank=True)
    
    # Summary fields
    non_taxable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    taxable_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_paid_to_supplier = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    local_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True, null=True)
    cgst = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    central_sales_tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    round_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_on_free_items = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_invoice_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    quotation_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    courier_transport_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    class Meta:
        db_table = 'travellers_in'
        ordering = ['-created_date']
    
    def __str__(self):
        return f"{self.invoice_no} - {self.vendor}"
    
    def save(self, *args, **kwargs):
        if self.pk:
            self.lastmodified_date = timezone.now()
        super().save(*args, **kwargs)

class TravellerIntent(AuditModel):
    itemName = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField()
    date = models.DateField()

    def __str__(self):
        return self.itemName