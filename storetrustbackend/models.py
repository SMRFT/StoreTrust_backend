from django.db import models, transaction
import datetime
from django.utils.timezone import now
from django.utils import timezone
import json

class AuditModel(models.Model):
    created_by = models.CharField(max_length=100, null=True, blank=True)

    created_date = models.DateTimeField(auto_now_add=True)
    lastmodified_by = models.CharField(max_length=100, blank=True, null=True)
    lastmodified_date = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        abstract = True


class TravellersIN(AuditModel):
    grn_id = models.IntegerField(unique=True, null=True, blank=True)
    grn_number = models.CharField(max_length=50, unique=True, null=True)

    payment_status = models.JSONField(default=list, blank=True, null=True)

    purchase_category = models.CharField(max_length=50, choices=[
        ('TRAVELLERS IN CREDIT', 'TRAVELLERS IN CREDIT'),
        ('TRAVELLERS IN CASH', 'TRAVELLERS IN CASH'),
    ])

    vendor_id = models.CharField(max_length=255, blank=True, null=True)

    date = models.DateField()
    invoice_no = models.CharField(max_length=100)
    invoice_date = models.DateField()

    credit_period = models.CharField(max_length=50, blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    payment_mode = models.CharField(max_length=50, blank=True, null=True)

    items = models.JSONField(default=list, blank=True)

    # Summary fields
    non_taxable_amount = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    taxable_amount = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    tax_paid_to_supplier = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    local_tax = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True, null=True)
    cgst = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    sgst = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    igst = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    cess = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    central_sales_tax = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    round_amount = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    tax_on_free_items = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    total_discount = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    net_invoice_amount = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    quotation_rate = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)
    courier_transport_charge = models.DecimalField(max_digits=50, decimal_places=2, default=0.00)

    class Meta:
        db_table = 'travellers_in'
        ordering = ['-created_date']

    def __str__(self):
        return f"{self.grn_number} - {self.vendor_id}"

    @staticmethod
    def get_financial_year_prefix():
        today = timezone.now().date()
        if today.month >= 4:
            return f"{today.year % 100}{(today.year + 1) % 100}"
        else:
            return f"{(today.year - 1) % 100}{today.year % 100}"

    @staticmethod
    def generate_grn_number(purchase_category):
        with transaction.atomic():
            prefix = TravellersIN.get_financial_year_prefix()

            last_record = (
                TravellersIN.objects
                .filter(
                    purchase_category=purchase_category,
                    grn_number__startswith=f"{prefix}/"
                )
                .order_by('-grn_number')
                .first()
            )

            if last_record and last_record.grn_number:
                last_seq = int(last_record.grn_number.split('/')[1])
                next_seq = last_seq + 1
            else:
                next_seq = 1

            return f"{prefix}/{next_seq:06d}"
        
    @staticmethod
    def generate_grn_id():
        last = TravellersIN.objects.order_by('-grn_id').first()
        return (last.grn_id + 1) if last and last.grn_id else 1

    def save(self, *args, **kwargs):
        if not self.grn_id:
            self.grn_id = self.generate_grn_id()

        if not self.grn_number:
            self.grn_number = self.generate_grn_number(self.purchase_category)

        if self.pk:
            self.lastmodified_date = timezone.now()

        super().save(*args, **kwargs)

class Vendors(AuditModel):
    supplierType = models.CharField(max_length=50, blank=True, null=True)
    vendor_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    name = models.CharField(max_length=255)
    addressLine1 = models.CharField(max_length=255)
    addressLine2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=20, blank=True, null=True)
    contactPerson = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    kgstTinNumber = models.CharField(max_length=50, blank=True, null=True)
    gstin = models.CharField(max_length=50)
    payment = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        db_table = 'vendors'
        verbose_name = 'Vendors'
        verbose_name_plural = 'Vendors'

    def __str__(self):
        return self.name

    def generate_vendor_id(self):
        """Generate auto-incrementing vendor_id starting from 1"""
        with transaction.atomic():
            try:
                # Get all vendors and find the maximum numeric vendor_id
                all_vendors = Vendors.objects.filter(vendor_id__isnull=False).values_list('vendor_id', flat=True)
                
                max_id = 0
                for vendor_id in all_vendors:
                    try:
                        numeric_id = int(vendor_id)
                        if numeric_id > max_id:
                            max_id = numeric_id
                    except (ValueError, TypeError):
                        continue
                
                new_id = max_id + 1
                
                # Ensure uniqueness
                while Vendors.objects.filter(vendor_id=str(new_id)).exists():
                    new_id += 1
                
                return str(new_id)
                
            except Exception as e:
                # Fallback: return "1" if there's any issue
                return "1"

    def save(self, *args, **kwargs):
        try:
            # Generate vendor_id if it's a new record and vendor_id is not provided
            if not self.pk and not self.vendor_id:
                self.vendor_id = self.generate_vendor_id()
            
            if self.pk:  # If updating existing record
                self.lastmodified_date = timezone.now()
            
            super().save(*args, **kwargs)
            
        except Exception as e:
            # Log the specific error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving vendor: {str(e)}")
            raise e  # Re-raise the exception



class Items(AuditModel):
    item_id = models.IntegerField(unique=True, blank=True, null=True)
    itemName = models.CharField(max_length=255)
    group = models.CharField(max_length=100)
    group_type = models.CharField(max_length=50, choices=[
        ('Service', 'Service'),
        ('Product', 'Product'), 
        ('Asset', 'Asset')
    ])
    category = models.CharField(max_length=100)
    classification = models.CharField(max_length=50)
    hsn = models.CharField(max_length=20, blank=True, null=True)
    stockReorderLevel = models.CharField(max_length=100)
    openingStock = models.IntegerField(default=0, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'items'
        verbose_name = 'Items'
        verbose_name_plural = 'Items'
    def __str__(self):
        return self.itemName

    def save(self, *args, **kwargs):
        if self.pk:
            # Updating existing record
            self.lastmodified_date = timezone.now()
        else:
            # Creating new record — auto-assign item_id if not provided
            if not self.item_id:
                last_item = Items.objects.order_by('-item_id').first()
                self.item_id = (last_item.item_id + 1) if last_item and last_item.item_id else 1
        super().save(*args, **kwargs)


class TravellerIntent(AuditModel):
    intent_number = models.CharField(max_length=20,primary_key=True, blank=True)
    items = models.JSONField(default=list)
    date = models.DateField() 
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Intent #{self.intent_number}"


class CollegeIntent(models.Model):
    intent_number = models.CharField(max_length=50, unique=True)
    date = models.DateField(default=timezone.now)
    items = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.intent_number


class MessIntent(AuditModel):
    intent_number = models.CharField(max_length=20, primary_key=True, blank=True)
    items = models.JSONField(default=list)
    date = models.DateField() 
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Intent #{self.intent_number}"


