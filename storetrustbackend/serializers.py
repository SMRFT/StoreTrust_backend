from rest_framework import serializers
from .models import TravellersIN
from bson import ObjectId

class TravellersINSerializer(serializers.ModelSerializer):
    # Handle ObjectId fields properly
    id = serializers.CharField(read_only=True)
    
    class Meta:
        model = TravellersIN
        fields = [
            'id',
            'purchase_category',
            'vendor',
            'date',
            'supplier_address',
            'contact_person',
            'phone',
            'invoice_no',
            'invoice_date',
            'credit_period',
            'due_date',
            'reference',
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
        read_only_fields = ['id', 'created_date', 'lastmodified_date']
    
    def to_representation(self, instance):
        """Convert ObjectId to string for JSON serialization"""
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
    
    
from .models import TravellerIntent
class TravellerIntentSerializer(serializers.ModelSerializer):
    id = ObjectIdField(read_only=True)
    class Meta:
        model = TravellerIntent
        fields = '__all__'