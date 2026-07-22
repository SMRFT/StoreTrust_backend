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

env_type  = os.environ.get("ENV_CLASSIFICATION", "local")
mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name   = os.environ.get("STORETRUST_DB_NAME", "StoreTrust")

_mongo_client = MongoClient(mongo_uri)
db = _mongo_client[db_name]

purchases_collection = db["travellers_in"]
intents_collection   = db["traveller_intent"]
items_collection     = db["items"]
vendors_collection   = db["vendors"]
store_collection     = db["store"]
stock_collection     = db["stock"]

def clean_mongo_document(doc):
    if isinstance(doc, dict):
        return {k: clean_mongo_document(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [clean_mongo_document(i) for i in doc]
    elif isinstance(doc, Decimal128):
        return float(doc.to_decimal())
    elif isinstance(doc, ObjectId):
        return str(doc)
    return doc



def update_or_create_opening_stock(item_id, hsn, opening_stock_val, outlet_code=None, employee_id=None):
    """
    Update or create opening stock in stock_collection for a given item_id and outlet_code.
    """
    if opening_stock_val is None:
        return
    try:
        op_qty = float(opening_stock_val)
    except (ValueError, TypeError):
        op_qty = 0.0

    try:
        item_id_int = int(item_id)
    except (ValueError, TypeError):
        item_id_int = item_id

    if not outlet_code:
        outlet_code = "OLET001"

    st_query = {
        "$or": [{"item_id": item_id_int}, {"item_id": str(item_id_int)}],
        "$and": [{"$or": [{"is_active": True}, {"is_active": {"$exists": False}}]}]
    }
    if outlet_code:
        st_query["outlet_code"] = outlet_code

    existing_st = stock_collection.find_one(st_query)

    if existing_st:
        stock_collection.update_one(
            {"_id": existing_st["_id"]},
            {
                "$set": {
                    "opening_stock": op_qty,
                    "hsn": str(hsn or existing_st.get("hsn", "")),
                    "lastmodified_by": str(employee_id or "Anonymous"),
                    "lastmodified_date": datetime.utcnow()
                }
            }
        )
    else:
        last_st = stock_collection.find_one(sort=[("stock_id", -1)])
        next_st_id = (last_st.get("stock_id", 0) + 1) if last_st and "stock_id" in last_st else 1
        st_doc = {
            "stock_id": next_st_id,
            "item_id": item_id_int if isinstance(item_id_int, int) else 0,
            "hsn": str(hsn or ""),
            "total_quantity": 0.0,
            "approved_quantity": 0.0,
            "opening_stock": op_qty,
            "outlet_code": outlet_code,
            "is_active": True,
            "created_by": str(employee_id or "Anonymous"),
            "created_date": datetime.utcnow()
        }
        stock_collection.insert_one(st_doc)


def get_item_stock_details(item_id, outlet_code=None):
    """
    Calculates total_stock = total_quantity + openingStock - approved_quantity
    scoped by outlet_code.
    """
    try:
        int_id = int(item_id)
    except (ValueError, TypeError):
        int_id = item_id

    query = {
        "$or": [{"item_id": int_id}, {"item_id": str(int_id)}],
        "$and": [{"$or": [{"is_active": True}, {"is_active": {"$exists": False}}]}]
    }
    if outlet_code:
        query["outlet_code"] = outlet_code

    stock_docs = list(stock_collection.find(query))

    if stock_docs:
        tot = sum(float(clean_mongo_document(s.get("total_quantity", 0)) or 0) for s in stock_docs)
        app = sum(float(clean_mongo_document(s.get("approved_quantity", 0)) or 0) for s in stock_docs)
        op_st = sum(float(clean_mongo_document(s.get("opening_stock", 0)) or 0) for s in stock_docs)
        total_st = tot + op_st - app
        return {
            "total_quantity": tot,
            "openingStock": op_st,
            "approved_quantity": app,
            "total_stock": total_st
        }
    else:
        if outlet_code:
            return {"total_quantity": 0.0, "openingStock": 0.0, "approved_quantity": 0.0, "total_stock": 0.0}
        item_doc = items_collection.find_one({
            "$or": [{"item_id": int_id}, {"item_id": str(int_id)}],
            "$and": [{"$or": [{"is_active": True}, {"is_active": {"$exists": False}}]}]
        })
        if item_doc:
            tot = float(clean_mongo_document(item_doc.get("total_quantity", 0)) or 0)
            op_st = float(clean_mongo_document(item_doc.get("openingStock", 0)) or 0)
            app = float(clean_mongo_document(item_doc.get("approved_quantity", 0)) or 0)
            total_st = tot + op_st - app
            return {
                "total_quantity": tot,
                "openingStock": op_st,
                "approved_quantity": app,
                "total_stock": total_st
            }
        return {"total_quantity": 0.0, "openingStock": 0.0, "approved_quantity": 0.0, "total_stock": 0.0}

@api_view(['GET'])
def list_outlets(request):
    try:
        if store_collection.count_documents({}) == 0:
            default_stores = [
                {
                    "outlet_name": "Travellers Inn",
                    "outlet_code": "OLET001",
                    "is_active": True,
                    "created_date": datetime.utcnow()
                },
                {
                    "outlet_name": "Mess",
                    "outlet_code": "OLET002",
                    "is_active": True,
                    "created_date": datetime.utcnow()
                },
                {
                    "outlet_name": "College",
                    "outlet_code": "OLET003",
                    "is_active": True,
                    "created_date": datetime.utcnow()
                }
            ]
            store_collection.insert_many(default_stores)

        outlets = list(store_collection.find({
            "$or": [
                {"is_active": True},
                {"is_active": {"$exists": False}}
            ]
        }))

        outlets_data = [clean_mongo_document(o) for o in outlets]
        return Response({"status": "success", "data": outlets_data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([HasRolePermission])
def create_outlet(request):
    try:
        data = request.data
        outlet_name = data.get("outlet_name")
        outlet_code = data.get("outlet_code")

        if not outlet_name or not outlet_code:
            return Response({"status": "error", "message": "outlet_name and outlet_code are required"}, status=status.HTTP_400_BAD_REQUEST)

        if store_collection.find_one({"outlet_code": outlet_code}):
            return Response({"status": "error", "message": "outlet_code already exists"}, status=status.HTTP_400_BAD_REQUEST)

        doc = {
            "outlet_name": outlet_name,
            "outlet_code": outlet_code,
            "is_active": True,
            "created_by": request.data.get("auth-user-id"),
            "created_date": datetime.utcnow()
        }
        res = store_collection.insert_one(doc)
        doc["id"] = str(res.inserted_id)
        return Response({"status": "success", "data": clean_mongo_document(doc)}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([HasRolePermission])
def list_stock(request):
    try:
        outlet_code = request.GET.get("outlet_code") or (request.data.get("outlet_code") if isinstance(request.data, dict) else None)
        query = {
            "$or": [
                {"is_active": True},
                {"is_active": {"$exists": False}}
            ]
        }
        if outlet_code:
            query["outlet_code"] = outlet_code

        stock_items = list(stock_collection.find(query))
        stock_data = [clean_mongo_document(s) for s in stock_items]
        return Response({"status": "success", "data": stock_data}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                    vendors_collection.update_one(
                        {"vendor_id": vendor_instance.vendor_id},
                        {"$unset": {"outlet_code": ""}}
                    )
                    logger.info(f"Vendor created successfully with ID: {vendor_instance.vendor_id}")
                    resp_data = VendorsSerializer(vendor_instance).data
                    resp_data.pop('outlet_code', None)
                    return Response(resp_data, status=status.HTTP_201_CREATED)
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
        vendors_collection = db["vendors"]

        # Fetch only active vendors
        def convert_decimal128(obj):
            if isinstance(obj, list):
                return [convert_decimal128(o) for o in obj]
            elif isinstance(obj, dict):
                return {k: convert_decimal128(v) for k, v in obj.items()}
            elif isinstance(obj, Decimal128):
                return float(obj.to_decimal())  # or str(obj.to_decimal())
            else:
                return obj

        vendors = list(vendors_collection.find({
            "$or": [
                {"is_active": True},
                {"is_active": {"$exists": False}}
            ]
        }))
        active_vendors = convert_decimal128(vendors)

        # Convert ObjectId to string and remove outlet_code if present
        for vendor in active_vendors:
            vendor["id"] = str(vendor["_id"])
            del vendor["_id"]
            vendor.pop("outlet_code", None)

        return Response(active_vendors, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": "Server error occurred", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
        vendors_collection.update_one(
            {"vendor_id": vendor_instance.vendor_id},
            {"$unset": {"outlet_code": ""}}
        )
        resp_data = VendorsSerializer(vendor_instance).data
        resp_data.pop('outlet_code', None)
        return Response(resp_data, status=status.HTTP_200_OK)

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
        # Ensure outlet_code is not stored in items collection
        items_collection.update_one(
            {"item_id": item_instance.item_id},
            {"$unset": {"outlet_code": ""}}
        )

        opening_stock_val = request.data.get("openingStock") if "openingStock" in request.data else request.data.get("opening_stock")
        if opening_stock_val is not None:
            outlet_code = request.data.get("outlet_code") or request.GET.get("outlet_code")
            update_or_create_opening_stock(
                item_id=item_instance.item_id,
                hsn=item_instance.hsn,
                opening_stock_val=opening_stock_val,
                outlet_code=outlet_code,
                employee_id=employee_id
            )
        data = ItemsSerializer(item_instance).data
        data.pop('outlet_code', None)
        return Response(data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([HasRolePermission])
def list_items(request):
    try:
        items_collection = db["items"]     # MongoDB collection object

        # Fetch only active items
        active_items = list(items_collection.find(
            {"$or": [
                {"is_active": True},
                {"is_active": {"$exists": False}}
            ]},
            {"_id": 1,"item_id": 1, "itemName": 1, "hsn": 1}
        ))

        # Convert ObjectId to string for JSON
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

@api_view(['PUT', 'PATCH'])
@permission_classes([HasRolePermission])
def update_item(request, item_id):

    try:
        item_id_int = int(item_id)
    except (ValueError, TypeError):
        return Response(
            {"status": "error", "message": f"Invalid item_id: {item_id}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    employee_id = request.data.get("auth-user-id")

    # ── Check item exists in MongoDB ──────────────────────────────────────
    existing = items_collection.find_one({"item_id": item_id_int})
    if not existing:
        return Response(
            {"status": "error", "message": f"Item not found for item_id={item_id_int}"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # ── Handle opening stock in stock collection ─────────────────────────────
    opening_stock_val = request.data.get("openingStock") if "openingStock" in request.data else request.data.get("opening_stock")
    if opening_stock_val is not None:
        outlet_code = request.data.get("outlet_code") or request.GET.get("outlet_code")
        hsn_val = request.data.get("hsn") or existing.get("hsn") or ""
        update_or_create_opening_stock(
            item_id=item_id_int,
            hsn=hsn_val,
            opening_stock_val=opening_stock_val,
            outlet_code=outlet_code,
            employee_id=employee_id
        )

    # ── Build update payload for items collection ─────────────────────────────
    allowed_fields = [
        "itemName", "group", "group_type", "category", "Category",
        "classification", "hsn", "stockReorderLevel",
        "is_active",
    ]

    update_fields = {}
    for field in allowed_fields:
        if field in request.data:
            update_fields[field] = request.data[field]

    # Audit fields
    update_fields["lastmodified_by"]   = str(employee_id)
    update_fields["lastmodified_date"] = datetime.utcnow()

    # ── Persist to MongoDB ────────────────────────────────────────────────
    items_collection.update_one(
        {"item_id": item_id_int},
        {"$set": update_fields, "$unset": {"outlet_code": ""}},
    )

    # ── Return updated document ───────────────────────────────────────────
    updated_doc = items_collection.find_one({"item_id": item_id_int})
    clean_doc = clean_mongo_document(updated_doc)
    if isinstance(clean_doc, dict):
        clean_doc.pop("outlet_code", None)
    return Response(
        {
            "status":  "success",
            "message": "Item updated successfully",
            "data":    clean_doc,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_item_dropdowns(request):
    """
    Returns all groups, categories, classifications in one call.
    Each entry is scoped so frontend can filter client-side.
    """
    # All unique groups
    groups = list(
        Items.objects.values_list('group', flat=True)
        .distinct().order_by('group')
    )

    # All unique categories with their group — for client-side filtering
    categories = list(
        Items.objects.values('group', 'category')
        .distinct().order_by('category')
    )

    # All unique classifications with group + category — for client-side filtering
    classifications = list(
        Items.objects.values('group', 'category', 'classification')
        .distinct().order_by('classification')
    )

    return Response({
        'groups':          groups,
        'categories':      categories,
        'classifications': classifications,
    }, status=status.HTTP_200_OK)


# ---- STOCK REORDER CHECK ENDPOINT (used by your Notifications.js) ----
@api_view(['GET'])
@permission_classes([HasRolePermission])
def stock_alerts(request):
    try:
        outlet_code = request.GET.get("outlet_code") or (request.data.get("outlet_code") if isinstance(request.data, dict) else None)
        low_stock = get_low_stock_items(outlet_code)
        return JsonResponse(low_stock, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
    
@api_view(["GET"])
def get_items(request):
    try:
        outlet_code = request.GET.get("outlet_code") or (request.data.get("outlet_code") if isinstance(request.data, dict) else None)
        items_collection = db["items"]     # MongoDB collection object

        stock_map = {}
        if outlet_code:
            st_query = {
                "outlet_code": outlet_code,
                "$or": [{"is_active": True}, {"is_active": {"$exists": False}}]
            }
            for s in stock_collection.find(st_query):
                i_id = s.get("item_id")
                if i_id is not None:
                    str_key = str(i_id)
                    if str_key not in stock_map:
                        stock_map[str_key] = {"tot": 0.0, "app": 0.0, "op": 0.0}
                    stock_map[str_key]["tot"] += float(clean_mongo_document(s.get("total_quantity", 0)) or 0)
                    stock_map[str_key]["app"] += float(clean_mongo_document(s.get("approved_quantity", 0)) or 0)
                    stock_map[str_key]["op"] += float(clean_mongo_document(s.get("opening_stock", 0)) or 0)

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

            if outlet_code:
                str_id = str(item.get("item_id"))
                st_info = stock_map.get(str_id, {"tot": 0.0, "app": 0.0, "op": 0.0})
                tot = st_info["tot"]
                op_st = st_info["op"]
                app = st_info["app"]
                avail = tot + op_st - app
                item_data["total_quantity"] = tot
                item_data["openingStock"] = op_st
                item_data["approved_quantity"] = app
                item_data["available_stock"] = avail
                item_data["total_stock"] = avail

            items.append(item_data)

        items.sort(key=lambda x: str(x.get("itemName") or "").strip().lower())
        return Response({"status": "success", "data": items}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(["PATCH"])
@permission_classes([HasRolePermission])
def delete_item(request, item_id):
    try:
        item_id_int = int(item_id)
    except (ValueError, TypeError):
        return Response(
            {"status": "error", "message": f"Invalid item_id: {item_id}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = items_collection.update_one(
        {"item_id": item_id_int},
        {"$set": {
            "is_active":          False,
            "lastmodified_by":    request.data.get("auth-user-id"),
            "lastmodified_date":  datetime.utcnow(),
        }}
    )

    if result.matched_count == 0:
        return Response(
            {"status": "error", "message": "Item not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    updated_doc = items_collection.find_one({"item_id": item_id_int})
    return Response(
        {
            "status":  "success",
            "message": "Item soft-deleted",
            "data":    clean_mongo_document(updated_doc),
        },
        status=status.HTTP_200_OK,
    )   


@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_vendors(request):
    try:
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