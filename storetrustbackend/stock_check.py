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
def get_low_stock_items():
    try:
        items_collection = db["items"]
        # Fetch only the required fields of active items to minimize query load
        items = items_collection.find(
            {"is_active": True},
            {"itemName": 1, "hsn": 1, "total_quantity": 1, "openingStock": 1, "approved_quantity": 1, "stockReorderLevel": 1}
        )
        low_stock_items = []
        for item in items:
            hsn = item.get("hsn", "")
            item_name = item.get("itemName", "")
            # total_quantity
            try:
                total_quantity = int(item.get("total_quantity", 0) or 0)
            except (ValueError, TypeError):
                logger.warning(f"Invalid total_quantity for {item_name} (HSN: {hsn}): {item.get('total_quantity')}")
                total_quantity = 0
            # openingStock
            try:
                opening_stock = int(item.get("openingStock", 0) or 0)
            except (ValueError, TypeError):
                opening_stock = 0
            # approved_quantity (optional, subtract if present)
            try:
                approved_quantity = int(item.get("approved_quantity", 0) or 0)
            except (ValueError, TypeError):
                approved_quantity = 0
            available_stock = total_quantity + opening_stock - approved_quantity
            # reorder level
            try:
                stock_reorder_level = int(item.get("stockReorderLevel", 0))
            except (ValueError, TypeError):
                logger.warning(f"Invalid stockReorderLevel for {item_name} (HSN: {hsn}): {item.get('stockReorderLevel')}")
                stock_reorder_level = 0
            logger.debug(f"Checking {item_name} (HSN {hsn}): available_stock={available_stock}, reorder_level={stock_reorder_level}")
            if available_stock < stock_reorder_level:
                low_stock_items.append({
                    "hsn": hsn,
                    "itemName": item_name,
                    "total_quantity": total_quantity,
                    "approved_quantity": approved_quantity,
                    "available_stock": available_stock,
                    "stockReorderLevel": stock_reorder_level,
                    "message": f"Stock for {item_name} (HSN: {hsn}) is {available_stock}, below reorder level {stock_reorder_level}"
                })
        logger.debug(f"Low stock items: {low_stock_items}")
        return low_stock_items
    except Exception as e:
        logger.error(f"Error in get_low_stock_items: {str(e)}", exc_info=True)
        raise
