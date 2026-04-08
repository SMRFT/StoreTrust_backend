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

    class Meta:
        model = TravellersIN
        fields = '__all__'
        read_only_fields = ['grn_id', 'created_date', 'grn_number']

    def to_representation(self, instance):
        ret = super().to_representation(instance)

        if hasattr(instance, '_id') and isinstance(instance._id, ObjectId):
            ret['_id'] = str(instance._id)

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




