from rest_framework import serializers
from .models import TravellersIN, TravellerIntent, Vendors, Items, CollegeIntent, MessIntent
from bson import ObjectId, Decimal128


class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        return str(value)
    def to_internal_value(self, data):
        return ObjectId(data)


class Decimal128Field(serializers.Field):
    def to_representation(self, value):
        if isinstance(value, Decimal128):
            return float(value.to_decimal())
        return float(value) if value is not None else None
    def to_internal_value(self, data):
        return Decimal128(str(data))

class TravellersINSerializer(serializers.ModelSerializer):
    grn_id = serializers.IntegerField(read_only=True)

    # ── Date fields: accept both date objects and YYYY-MM-DD strings ──────
    date         = serializers.DateField(required=False, allow_null=True)
    invoice_date = serializers.DateField(required=False, allow_null=True)
    due_date     = serializers.DateField(required=False, allow_null=True)

    # ── Audit fields: writable so the view can set them on update ─────────
    lastmodified_by   = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    lastmodified_date = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = TravellersIN
        fields = [
            'grn_id',
            'purchase_category',
            'vendor_id',
            'grn_number',
            'payment_status',
            'date',
            'invoice_no',
            'invoice_date',
            'credit_period',
            'due_date',
            'payment_mode',
            'items',
            'non_taxable_amount',
            'taxable_amount',
            'tax_paid_to_supplier',
            'local_tax',
            'remarks',
            'cgst',
            'sgst',
            'igst',
            'cess',
            'central_sales_tax',
            'round_amount',
            'total_amount',
            'tax_on_free_items',
            'total_discount',
            'net_invoice_amount',
            'quotation_rate',
            'courier_transport_charge',
            'created_by',
            'created_date',
            'lastmodified_by',
            'lastmodified_date',
        ]
        # created_date is read-only; lastmodified_date is now writable above
        read_only_fields = ['grn_id', 'created_date']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if isinstance(ret.get('id'), ObjectId):
            ret['id'] = str(ret['id'])
        return ret

    def create(self, validated_data):
        return TravellersIN.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance
    

class ObjectIdField(serializers.Field):
    def to_representation(self, value):
        return str(value)
    def to_internal_value(self, data):
        return ObjectId(data)

class TravellerIntentSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True)
    class Meta:
        model = TravellerIntent
        fields = '__all__'



class VendorsSerializer(serializers.ModelSerializer):
    created_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    lastmodified_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    id = serializers.SerializerMethodField()  # Convert ObjectId to string if needed

    def get_id(self, obj):
        return str(obj.id) if isinstance(obj.id, ObjectId) else obj.id

    class Meta:
        model = Vendors
        fields = "__all__"
        # Make audit fields read-only since we'll set them programmatically
        read_only_fields = ['created_by', 'created_date', 'lastmodified_by', 'lastmodified_date']

    def create(self, validated_data):
        # Get the employee_id from the context (passed from the view)
        employee_id = self.context.get('employee_id')
        
        # Set the created_by field
        if employee_id:
            validated_data['created_by'] = employee_id
            
        return super().create(validated_data)

    def update(self, instance, validated_data):
        # Get the employee_id from the context (passed from the view)
        employee_id = self.context.get('employee_id')
        
        # Set the lastmodified_by field
        if employee_id:
            validated_data['lastmodified_by'] = employee_id
            
        return super().update(instance, validated_data)



class ItemsSerializer(serializers.ModelSerializer):
    created_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    lastmodified_date = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", required=False)
    id = serializers.SerializerMethodField()

    def get_id(self, obj):
        return str(obj.id) if isinstance(obj.id, ObjectId) else obj.id

    class Meta:
        model = Items
        fields = "__all__"
        read_only_fields = ['created_by', 'created_date', 'lastmodified_by', 'lastmodified_date']

    def create(self, validated_data):
        employee_id = self.context.get('employee_id')
        if employee_id:
            validated_data['created_by'] = employee_id
        return super().create(validated_data)

    def update(self, instance, validated_data):
        employee_id = self.context.get('employee_id')
        if employee_id:
            validated_data['lastmodified_by'] = employee_id
        return super().update(instance, validated_data)

class CollegeIntentSerializer(serializers.ModelSerializer):
   created_by = serializers.CharField() 
   class Meta:
        model = CollegeIntent
        fields = "__all__"

class MessIntentSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True)
    class Meta:
        model = MessIntent
        fields = '__all__'




