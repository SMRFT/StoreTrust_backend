from rest_framework.decorators import api_view, permission_classes
from pyauth.auth import HasRolePermission
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from datetime import datetime
from django.conf import settings
from django.db import transaction
import traceback
import logging
from django.http import JsonResponse
from .models import Vendors, Items
from .serializers import VendorsSerializer, ItemsSerializer
import os
from dotenv import load_dotenv
import certifi
from pymongo import MongoClient
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.decimal128 import Decimal128
from datetime import datetime
from .stock_check import get_low_stock_items
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from pymongo import MongoClient
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from pymongo import MongoClient
from bson.decimal128 import Decimal128
from bson import json_util

logger = logging.getLogger(__name__)
load_dotenv()

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("STORETRUST_DB_NAME", "StoreTrust")

if env_type in ["test", "prod"]:
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri)

@api_view(['POST'])
@permission_classes([HasRolePermission])
def create_vendor(request):
    """
    Create a new vendor with auto-generated vendor_id
    """
    try:
        employee_id = request.data.get('auth-user-id')
        logger.info(f"Creating vendor with data: {request.data}")

        request_data = request.data.copy()
        if 'vendor_id' in request_data:
            del request_data['vendor_id']

        serializer = VendorsSerializer(data=request_data, context={'employee_id': employee_id})

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    vendor_instance = serializer.save(
                        created_by=employee_id,
                        created_date=datetime.now()
                    )
                    logger.info(f"Vendor created successfully with ID: {vendor_instance.vendor_id}")
                    return Response(VendorsSerializer(vendor_instance).data, status=status.HTTP_201_CREATED)
            except Exception as e:
                error_message = str(e)
                error_traceback = traceback.format_exc()
                logger.error(f"Database error creating vendor: {error_message}\n{error_traceback}")
                return Response(
                    {
                        'error': f'Failed to create vendor: {error_message}',
                        'details': error_traceback if getattr(settings, "DEBUG", False) else None
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
            logger.warning(f"Validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        error_message = str(e)
        error_traceback = traceback.format_exc()
        logger.error(f"Unexpected error in create_vendor: {error_message}\n{error_traceback}")
        return Response(
            {
                'error': f'Unexpected error: {error_message}',
                'details': error_traceback if getattr(settings, "DEBUG", False) else None
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@api_view(['GET'])
@permission_classes([HasRolePermission])
def list_vendors(request):
    try:
        DB_NAME = "StoreTrust"
        COLLECTION_NAME = "vendors"
        # 1️⃣ Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client[DB_NAME]
        vendors_collection = db[COLLECTION_NAME]

        # 2️⃣ Ensure all documents have `is_active`
        vendors_collection.update_many(
            {"is_active": {"$exists": False}},
            {"$set": {"is_active": True}}
        )

        # 3️⃣ Fetch only active vendors
        def convert_decimal128(obj):
            if isinstance(obj, list):
                return [convert_decimal128(o) for o in obj]
            elif isinstance(obj, dict):
                return {k: convert_decimal128(v) for k, v in obj.items()}
            elif isinstance(obj, Decimal128):
                return float(obj.to_decimal())  # or str(obj.to_decimal())
            else:
                return obj

        vendors = list(vendors_collection.find({"is_active": True}))
        active_vendors = convert_decimal128(vendors)

        # 4️⃣ Convert ObjectId to string
        for vendor in active_vendors:
            vendor["id"] = str(vendor["_id"])
            del vendor["_id"]

        return Response(active_vendors, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": "Server error occurred", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendors, id=vendor_id)
    serializer = VendorsSerializer(vendor)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([HasRolePermission])
def update_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendors, id=vendor_id)
    employee_id = request.data.get('auth-user-id')

    serializer = VendorsSerializer(
        vendor,
        data=request.data,
        context={'employee_id': employee_id},
        partial=True
    )

    if serializer.is_valid():
        vendor_instance = serializer.save(
            lastmodified_by=employee_id,
            lastmodified_date=datetime.now()
        )
        return Response(VendorsSerializer(vendor_instance).data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def delete_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendors, id=vendor_id)
    vendor.delete()
    return Response({'message': 'Vendor deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([HasRolePermission])
def create_item(request):
    employee_id = request.data.get('auth-user-id')
    serializer = ItemsSerializer(data=request.data, context={'employee_id': employee_id})

    if serializer.is_valid():
        item_instance = serializer.save(
            created_by=employee_id,
            created_date=datetime.now()
        )
        return Response(ItemsSerializer(item_instance).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([HasRolePermission])
def list_items(request):
    try:
        # 1️⃣ Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client[db_name]               # MongoDB database object
        items_collection = db["items"]     # MongoDB collection object

        # 2️⃣ Ensure all documents have is_active
        items_collection.update_many(
            {"is_active": {"$exists": False}},
            {"$set": {"is_active": True}}
        )

        # 3️⃣ Fetch only active items
        active_items = list(items_collection.find(
            {"is_active": True},
            {"_id": 1, "itemName": 1, "hsn": 1}
        ))

        # 4️⃣ Convert ObjectId to string for JSON
        for item in active_items:
            item["id"] = str(item["_id"])
            del item["_id"]

        return Response(active_items, status=status.HTTP_200_OK)

    except Exception as e:
        # Catch all exceptions and return details
        return Response(
            {"error": "Server error occurred", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_item(request, item_id):
    item = get_object_or_404(Items, id=item_id)
    serializer = ItemsSerializer(item)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([HasRolePermission])
def update_item(request, item_id):
    item = get_object_or_404(Items, id=item_id)
    employee_id = request.data.get('auth-user-id')

    serializer = ItemsSerializer(
        item,
        data=request.data,
        context={'employee_id': employee_id},
        partial=True
    )

    if serializer.is_valid():
        item_instance = serializer.save(
            lastmodified_by=employee_id,
            lastmodified_date=datetime.now()
        )
        return Response(ItemsSerializer(item_instance).data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def delete_item(request, item_id):
    item = get_object_or_404(Items, id=item_id)
    item.delete()
    return Response({'message': 'Item deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

@permission_classes([HasRolePermission])
@api_view(['GET'])
def get_groups(request):
    groups = Items.objects.values_list('group', flat=True).distinct().order_by('group')
    return Response(list(groups), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_categories(request):
    group = request.GET.get('group')
    if group:
        categories = Items.objects.filter(group=group).values_list('category', flat=True).distinct().order_by('category')
    else:
        categories = Items.objects.values_list('category', flat=True).distinct().order_by('category')
    return Response(list(categories), status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_classifications(request):
    group = request.GET.get('group')
    category = request.GET.get('category')

    queryset = Items.objects.all()
    if group:
        queryset = queryset.filter(group=group)
    if category:
        queryset = queryset.filter(category=category)

    classifications = queryset.values_list('classification', flat=True).distinct().order_by('classification')
    return Response(list(classifications), status=status.HTTP_200_OK)


# ---- STOCK REORDER CHECK ENDPOINT (used by your Notifications.js) ----
@api_view(['GET'])
@permission_classes([HasRolePermission])
def stock_alerts(request):
    try:
        low_stock = get_low_stock_items()
        return JsonResponse(low_stock, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@api_view(["GET"])
@permission_classes([HasRolePermission])
def get_items(request):
    try:
        
        client = MongoClient(mongo_uri)
        db = client[db_name]               # MongoDB database object
        items_collection = db["items"]     # MongoDB collection object
        # Fetch only active items
        items_cursor = items_collection.find({
            "$or": [
                {"is_active": True},
                {"is_active": {"$exists": False}}
            ]
        })

        items = []
        for item in items_cursor:
            item_data = {}
            for key, value in item.items():
                if isinstance(value, ObjectId):
                    item_data[key] = str(value)
                elif isinstance(value, Decimal128):
                    item_data[key] = float(value.to_decimal())
                elif isinstance(value, datetime):
                    item_data[key] = value.isoformat()
                else:
                    item_data[key] = value
            items.append(item_data)

        return Response({"status": "success", "data": items}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["PATCH"])
@permission_classes([HasRolePermission])
def update_item(request, item_id):
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        items_collection = db["items"]
        
        # Get only the business data, exclude auth fields
        data = request.data.copy()
        
        # Remove _id and all auth-related fields
        fields_to_remove = ["_id"]
        auth_fields = [key for key in data.keys() if key.startswith("auth-")]
        fields_to_remove.extend(auth_fields)
        
        for field in fields_to_remove:
            data.pop(field, None)
        
        # Add audit fields directly
        data["lastmodified_by"] = request.data.get("auth-user-id")
        data["lastmodified_date"] = datetime.now()

        result = items_collection.update_one(
            {"_id": ObjectId(item_id)}, 
            {"$set": data}
        )
        
        if result.matched_count == 0:
            return Response(
                {"status": "error", "message": "Item not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        updated_item = items_collection.find_one({"_id": ObjectId(item_id)})
        
        # Convert MongoDB types to JSON-serializable types
        for key, value in updated_item.items():
            if isinstance(value, ObjectId):
                updated_item[key] = str(value)
            elif isinstance(value, Decimal128):
                updated_item[key] = float(value.to_decimal())
            elif isinstance(value, datetime):
                updated_item[key] = value.isoformat()

        return Response(
            {"status": "success", "data": updated_item}, 
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["PATCH"])
@permission_classes([HasRolePermission])
def delete_item(request, item_id):
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        items_collection = db["items"]
        
        result = items_collection.update_one(
            {"_id": ObjectId(item_id)},
            {"$set": {
                "is_active": False,
                "lastmodified_by": request.data.get("auth-user-id"),
                "lastmodified_date": datetime.now()
            }}
        )
        
        if result.matched_count == 0:
            return Response(
                {"status": "error", "message": "Item not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        updated_item = items_collection.find_one({"_id": ObjectId(item_id)})
        
        # Convert MongoDB types to JSON-serializable types
        for key, value in updated_item.items():
            if isinstance(value, ObjectId):
                updated_item[key] = str(value)
            elif isinstance(value, Decimal128):
                updated_item[key] = float(value.to_decimal())
            elif isinstance(value, datetime):
                updated_item[key] = value.isoformat()

        return Response(
            {"status": "success", "data": updated_item, "message": "Item soft-deleted"}, 
            status=status.HTTP_200_OK
        )
        
    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    


@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_vendors(request):
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        vendors_collection = db["vendors"]
        # Fetch vendors where is_active is True or not set
        vendors_cursor = vendors_collection.find({
            "$or": [
                {"is_active": True},
                {"is_active": {"$exists": False}}
            ]
        })

        vendors = []
        for vendor in vendors_cursor:
            vendor_data = {}
            for key, value in vendor.items():
                if isinstance(value, ObjectId):
                    vendor_data[key] = str(value)
                elif isinstance(value, Decimal128):
                    vendor_data[key] = float(value.to_decimal())
                elif isinstance(value, datetime):
                    vendor_data[key] = value.isoformat()
                else:
                    vendor_data[key] = value
            vendors.append(vendor_data)

        return Response({"status": "success", "data": vendors}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ✅ UPDATE vendor (PATCH)
@api_view(["PATCH"])
@permission_classes([HasRolePermission])
def update_vendor(request, vendor_id):
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        vendors_collection = db["vendors"]
        
        # Get only the business data, exclude auth fields
        data = request.data.copy()
        
        # Remove _id and all auth-related fields
        fields_to_remove = ["_id"]
        auth_fields = [key for key in data.keys() if key.startswith("auth-")]
        fields_to_remove.extend(auth_fields)
        
        for field in fields_to_remove:
            data.pop(field, None)
        
        # Add audit fields directly
        data["lastmodified_by"] = request.data.get("auth-user-id")
        data["lastmodified_date"] = datetime.now()

        # Perform the update
        result = vendors_collection.update_one(
            {"_id": ObjectId(vendor_id)}, 
            {"$set": data}
        )

        # Check if a document was matched
        if result.matched_count == 0:
            return Response(
                {"status": "error", "message": "Vendor not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Fetch the updated document
        updated_vendor = vendors_collection.find_one({"_id": ObjectId(vendor_id)})

        # Convert ObjectId, Decimal128, datetime inline
        for key, value in updated_vendor.items():
            if isinstance(value, ObjectId):
                updated_vendor[key] = str(value)
            elif isinstance(value, Decimal128):
                updated_vendor[key] = float(value.to_decimal())
            elif isinstance(value, datetime):
                updated_vendor[key] = value.isoformat()

        return Response(
            {"status": "success", "data": updated_vendor}, 
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ✅ Soft DELETE vendor (PATCH)
@api_view(["PATCH"])
@permission_classes([HasRolePermission])
def delete_vendor(request, vendor_id):
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        vendors_collection = db["vendors"]
        
        # Soft delete: set is_active to False with audit fields
        result = vendors_collection.update_one(
            {"_id": ObjectId(vendor_id)},
            {"$set": {
                "is_active": False,
                "lastmodified_by": request.data.get("auth-user-id"),
                "lastmodified_date": datetime.now()
            }}
        )

        if result.matched_count == 0:
            return Response(
                {"status": "error", "message": "Vendor not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Fetch updated vendor
        updated_vendor = vendors_collection.find_one({"_id": ObjectId(vendor_id)})

        # Convert ObjectId, Decimal128, datetime inline
        for key, value in updated_vendor.items():
            if isinstance(value, ObjectId):
                updated_vendor[key] = str(value)
            elif isinstance(value, Decimal128):
                updated_vendor[key] = float(value.to_decimal())
            elif isinstance(value, datetime):
                updated_vendor[key] = value.isoformat()

        return Response(
            {"status": "success", "data": updated_vendor, "message": "Vendor soft-deleted"},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )