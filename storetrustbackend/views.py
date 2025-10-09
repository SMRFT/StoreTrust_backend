from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from pymongo import MongoClient
from bson.decimal128 import Decimal128
from bson.objectid import ObjectId
from datetime import datetime

# MongoDB connection
mongo_url = "mongodb://admin:YSEgnm42789@103.205.141.245:27017/"
client = MongoClient(mongo_url)
db = client["StoreTrust"]
vendors_collection = db["vendors"]

# ===== GET active vendors =====
@api_view(['GET'])
def get_vendors(request):
    try:
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

@api_view(["POST"])
def create_vendor(request):
    try:
        data = request.data
        result = vendors_collection.insert_one(data)
        new_vendor = vendors_collection.find_one({"_id": result.inserted_id})

        # Convert ObjectId and Decimal128
        for key, value in new_vendor.items():
            if isinstance(value, ObjectId):
                new_vendor[key] = str(value)
            elif isinstance(value, Decimal128):
                new_vendor[key] = float(value.to_decimal())
            elif isinstance(value, datetime):
                new_vendor[key] = value.isoformat()

        return Response({"status": "success", "data": new_vendor}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ UPDATE vendor (PATCH)
@api_view(["PATCH"])
def update_vendor(request, vendor_id):
    try:
        data = request.data.copy()      # copy the dict
        data.pop("_id", None)           # remove _id to avoid MongoDB error

        # Perform the update
        result = vendors_collection.update_one({"_id": ObjectId(vendor_id)}, {"$set": data})

        # Check if a document was matched
        if result.matched_count == 0:
            return Response({"status": "error", "message": "Vendor not found"}, status=status.HTTP_404_NOT_FOUND)

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

        return Response({"status": "success", "data": updated_vendor}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ✅ Soft DELETE vendor (PATCH)
@api_view(["PATCH"])
def delete_vendor(request, vendor_id):
    try:
        # Soft delete: set is_active to False
        result = vendors_collection.update_one(
            {"_id": ObjectId(vendor_id)},
            {"$set": {"is_active": False}}
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
            {"status": "success", "data": updated_vendor},
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# items edit 

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.decimal128 import Decimal128
from datetime import datetime

# MongoDB connection
mongo_url = "mongodb://admin:YSEgnm42789@103.205.141.245:27017/"
client = MongoClient(mongo_url)
db = client["StoreTrust"]
items_collection = db["items"]

# ===== GET all items =====
@api_view(["GET"])
def get_items(request):
    try:
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

# ===== CREATE item =====
@api_view(["POST"])
def create_item(request):
    try:
        data = request.data
        result = items_collection.insert_one(data)
        new_item = items_collection.find_one({"_id": result.inserted_id})

        # convert _id, Decimal128, datetime
        for key, value in new_item.items():
            if isinstance(value, ObjectId):
                new_item[key] = str(value)
            elif isinstance(value, Decimal128):
                new_item[key] = float(value.to_decimal())
            elif isinstance(value, datetime):
                new_item[key] = value.isoformat()

        return Response({"status": "success", "data": new_item}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== UPDATE item =====
@api_view(["PATCH"])
def update_item(request, item_id):
    try:
        data = request.data.copy()
        data.pop("_id", None)

        result = items_collection.update_one({"_id": ObjectId(item_id)}, {"$set": data})
        if result.matched_count == 0:
            return Response({"status": "error", "message": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

        updated_item = items_collection.find_one({"_id": ObjectId(item_id)})
        for key, value in updated_item.items():
            if isinstance(value, ObjectId):
                updated_item[key] = str(value)
            elif isinstance(value, Decimal128):
                updated_item[key] = float(value.to_decimal())
            elif isinstance(value, datetime):
                updated_item[key] = value.isoformat()

        return Response({"status": "success", "data": updated_item}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===== DELETE item =====
@api_view(["PATCH"])
def delete_item(request, item_id):
    try:
        result = items_collection.update_one(
            {"_id": ObjectId(item_id)},
            {"$set": {"is_active": False}}
        )
        if result.matched_count == 0:
            return Response({"status": "error", "message": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

        updated_item = items_collection.find_one({"_id": ObjectId(item_id)})
        for key, value in updated_item.items():
            if isinstance(value, ObjectId):
                updated_item[key] = str(value)
            elif isinstance(value, Decimal128):
                updated_item[key] = float(value.to_decimal())
            elif isinstance(value, datetime):
                updated_item[key] = value.isoformat()

        return Response({"status": "success", "data": updated_item, "message": "Item soft-deleted"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
