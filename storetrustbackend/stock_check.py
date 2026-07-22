import os
import json
import certifi
import logging
from pymongo import MongoClient
from rest_framework.decorators import api_view, permission_classes
from pyauth.auth import HasRolePermission
from dotenv import load_dotenv
logger = logging.getLogger(__name__)
load_dotenv()

# Global MongoDB client initialized once at module load
env_type = os.environ.get("ENV_CLASSIFICATION", "local")
mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("STORETRUST_DB_NAME", "StoreTrust")
_mongo_client = MongoClient(mongo_uri)
db = _mongo_client[db_name]

@permission_classes([HasRolePermission])
def get_low_stock_items(outlet_code=None):
    try:
        items_collection = db["items"]
        stock_collection = db["stock"]

        # Batch query stock collection by outlet_code to prevent N queries in a loop
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
                    stock_map[str_key]["tot"] += float(s.get("total_quantity", 0) or 0)
                    stock_map[str_key]["app"] += float(s.get("approved_quantity", 0) or 0)
                    stock_map[str_key]["op"] += float(s.get("opening_stock", 0) or 0)

        items = items_collection.find(
            {"$or": [{"is_active": True}, {"is_active": {"$exists": False}}]},
            {"item_id": 1, "itemName": 1, "hsn": 1, "total_quantity": 1, "openingStock": 1, "approved_quantity": 1, "stockReorderLevel": 1, "outlet_code": 1}
        )

        low_stock_items = []
        for item in items:
            item_id = item.get("item_id")
            if item_id is None:
                continue
            hsn = item.get("hsn", "")
            item_name = item.get("itemName", "")
            str_id = str(item_id)

            if outlet_code:
                if str_id in stock_map:
                    st_info = stock_map[str_id]
                    total_quantity = st_info["tot"]
                    approved_quantity = st_info["app"]
                    opening_stock = st_info["op"]
                else:
                    item_outlet = item.get("outlet_code")
                    if item_outlet and item_outlet != outlet_code:
                        total_quantity = 0.0
                        approved_quantity = 0.0
                        opening_stock = 0.0
                    else:
                        total_quantity = float(item.get("total_quantity", 0) or 0)
                        approved_quantity = float(item.get("approved_quantity", 0) or 0)
                        opening_stock = float(item.get("openingStock", 0) or 0)
            else:
                total_quantity = float(item.get("total_quantity", 0) or 0)
                approved_quantity = float(item.get("approved_quantity", 0) or 0)
                opening_stock = float(item.get("openingStock", 0) or 0)

            available_stock = total_quantity + opening_stock - approved_quantity

            try:
                stock_reorder_level = float(item.get("stockReorderLevel", 0) or 0)
            except (ValueError, TypeError):
                stock_reorder_level = 0.0

            if available_stock < stock_reorder_level:
                low_stock_items.append({
                    "hsn": hsn,
                    "itemName": item_name,
                    "total_quantity": total_quantity,
                    "approved_quantity": approved_quantity,
                    "opening_stock": opening_stock,
                    "available_stock": available_stock,
                    "stockReorderLevel": stock_reorder_level,
                    "message": f"Stock for {item_name} (HSN: {hsn}) is {available_stock}, below reorder level {stock_reorder_level}"
                })
        return low_stock_items
    except Exception as e:
        logger.error(f"Error in get_low_stock_items: {str(e)}", exc_info=True)
        return []
        raise
