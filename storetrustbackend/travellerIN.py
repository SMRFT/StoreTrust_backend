from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
import json
from .models import TravellersIN ,Vendors
from .serializers import TravellersINSerializer
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .models import TravellerIntent
from .serializers import TravellerIntentSerializer
from pyauth.auth import HasRolePermission
from pymongo import MongoClient
from django.conf import settings
import logging
from storetrustbackend.database import get_database
from decimal import Decimal
from bson.decimal128 import Decimal128
import os
from dotenv import load_dotenv
logger = logging.getLogger(__name__)
import certifi
from .models import Items
from .serializers import ItemsSerializer



load_dotenv()

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("STORETRUST_DB_NAME", "StoreTrust")

if env_type in ["test", "prod"]:
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri)
    

@csrf_exempt
@permission_classes([HasRolePermission])
def update_stock_by_hsn(items):
    """
    Update total stock for each HSN in items list
    """
    items_collection = db["items"]  # adjust if your stock collection name differs
    for item in items:
        hsn = item.get("hsn")
        qty = int(item.get("totalstock", 0))
        if hsn and qty > 0:
            # print(items_collection.find("total_quantity"))
            result = items_collection.find_one_and_update(
                {"hsn": hsn},
                {"$inc": {"total_quantity": qty}},
                return_document=True
            )
            if not result:
                # Item with HSN not found -> log this
                print(f"No item found for HSN {hsn}, stock not updated.")
                
@csrf_exempt
@api_view(['POST'])
@permission_classes([HasRolePermission])
def create_travellers_in(request):
    """
    Create a new TravellersIN record with auto-generated GRN number
    """
    try:
        data = request.data
        
        # Map frontend field names to backend field names
        mapped_data = {
            'purchase_category': data.get('purchaseCategory'),
            'vendor_id': data.get('vendor_id'),
            'date': data.get('date'),            
            'invoice_no': data.get('invoiceNo'),
            'invoice_date': data.get('invoiceDate'),
            'credit_period': data.get('creditPeriod'),
            'due_date': data.get('dueDate'),
            'payment_mode': data.get('paymentMode'),
            'items': data.get('items', []),
        }
        
        # Map summary fields
        summary = data.get('summary', {})
        summary_mapping = {
            'non_taxable_amount': 'nonTaxableAmount',
            'taxable_amount': 'taxableAmount',
            'tax_paid_to_supplier': 'taxPaidToSupplier',
            'local_tax': 'localTax',
            'remarks': 'remarks',
            'cgst': 'cgst',
            'sgst': 'sgst',
            'igst': 'igst',
            'cess': 'cess',
            'central_sales_tax': 'centralSalesTax',
            'round_amount': 'roundAmount',
            'total_amount': 'totalAmount',
            'tax_on_free_items': 'taxOnFreeItems',
            'total_discount': 'totalDiscount',
            'net_invoice_amount': 'netInvoiceAmount',
            'quotation_rate': 'quotationRate',
            'courier_transport_charge': 'courierTransportCharge',
        }
        
        for backend_field, frontend_field in summary_mapping.items():
            mapped_data[backend_field] = summary.get(frontend_field, 0)
        
        # Add audit fields - UPDATED to use auth-user-id from request data
        employee_id = data.get('auth-user-id')
        mapped_data['created_by'] = employee_id if employee_id else 'Anonymous'
        print(f"Creating TravellersIN record with created_by: {mapped_data['created_by']}")
        mapped_data['is_active'] = True
                # Initialize payment_status as an array
        total_amount = float(mapped_data.get('total_amount', 0))
        mapped_data['payment_status'] = [{
            'status': 'Not Paid',
            'amount_paid': 0.0,
            'pending_amount': total_amount,
            'payment_method': None,
            'payment_details': None,
            'paid_by': None
        }]
        mapped_data['overall_payment_status'] = 'Not Paid'

        # Note: GRN number will be auto-generated in the model's save method
        serializer = TravellersINSerializer(data=mapped_data)
        if serializer.is_valid():
            travellers_in = serializer.save()
            # :white_check_mark: Call stock update by HSN
            update_stock_by_hsn(mapped_data['items'])
            return JsonResponse({
                'status': 'success',
                'message': 'TravellersIN record created successfully',
                'grn_number': travellers_in.grn_number,  # Return the generated GRN number
                'data': TravellersINSerializer(travellers_in).data
            }, status=201)
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

    
# Set up logging
logger = logging.getLogger(__name__)

from bson import Decimal128
from decimal import Decimal
import traceback
import urllib

def convert_decimal128_to_float(value):
    """Convert Decimal128 or other numeric types to float safely"""
    if value is None:
        return 0.0
    
    if isinstance(value, Decimal128):
        return float(value.to_decimal())
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, (int, float)):
        return float(value)
    elif isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    else:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

@csrf_exempt
@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_travellers_in_list(request):
    """
    Get list of TravellersIN records with pagination (only active records), including vendor details
    """
    try:
        # Log request details for debugging
        logger.debug(f"Request headers: {request.headers}")
        logger.debug(f"Request user: {request.user}, Query params: {request.GET}")

        # Get all records, ordered by created_date
        all_records = TravellersIN.objects.all().order_by('-created_date')
        
        # Filter for active records
        active_records = [
            record for record in all_records
            if str(getattr(record, 'is_active', False)).lower() in ('true', '1')
        ]
        
        # Handle pagination parameters safely
        try:
            page = int(request.GET.get('page', 1))
            page_size = int(request.GET.get('page_size', 10))
            if page < 1:
                logger.warning("Invalid page number, defaulting to 1")
                page = 1
            if page_size < 1:
                logger.warning("Invalid page size, defaulting to 10")
                page_size = 10
        except ValueError:
            logger.warning("Invalid page or page_size format, using defaults")
            page = 1
            page_size = 10
        
        # Calculate pagination
        total_records = len(active_records)
        total_pages = (total_records + page_size - 1) // page_size
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        page_records = active_records[start_index:end_index]
        
        # Create response data
        response_data = []
        for obj in page_records:
            try:
                # Fetch vendor details
                vendor_details = {
                    'vendor': '',
                    'contact_person': '',
                    'phone': '',
                    'address': '',
                    'email': ''
                }
                if obj.vendor_id:
                    try:
                        vendor = Vendors.objects.get(vendor_id=obj.vendor_id)
                        vendor_details = {
                            'vendor': vendor.name,
                            'contact_person': vendor.contactPerson or '',
                            'phone': vendor.phone or '',
                            'address': f"{vendor.addressLine1}, {vendor.addressLine2 }, {vendor.city}, {vendor.state or ''}".strip(', '),
                            'email': vendor.email or ''
                        }
                    except Vendors.DoesNotExist:
                        logger.warning(f"Vendor with vendor_id {obj.vendor_id} not found")
                
                # Handle items field
                items = getattr(obj, 'items', [])
                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                        if not isinstance(items, list):
                            logger.warning(f"Items field for GRN {obj.grn_number} is a string but not a valid JSON list")
                            items = []
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in items for GRN {obj.grn_number}")
                        items = []
                elif isinstance(items, list):
                    pass
                else:
                    logger.warning(f"Items field for GRN {obj.grn_number} is neither a string nor a list")
                    items = []
                
                # Convert numeric fields in items
                for item in items:
                    numeric_item_fields = [
                        'itemValue', 'packingPrice', 'unitPrice', 'cgstAmt', 'sgstAmt',
                        'purchaseCost', 'mrp', 'tax', 'cgstPercent', 'sgstPercent'
                    ]
                    for field in numeric_item_fields:
                        if field in item:
                            item[field] = convert_decimal128_to_float(item[field])
                
                # Handle payment_status field
                payment_status = getattr(obj, 'payment_status', [])
                if isinstance(payment_status, str):
                    try:
                        payment_status = json.loads(payment_status)
                        if not isinstance(payment_status, list):
                            logger.warning(f"payment_status for GRN {obj.grn_number} is a string but not a valid JSON list")
                            payment_status = []
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON in payment_status for GRN {obj.grn_number}")
                        payment_status = []
                elif isinstance(payment_status, list):
                    pass
                else:
                    logger.warning(f"payment_status for GRN {obj.grn_number} is neither a string nor a list")
                    payment_status = []
                
                # Convert numeric fields in payment_status
                for entry in payment_status:
                    numeric_payment_fields = ['amount_paid', 'pending_amount']
                    for field in numeric_payment_fields:
                        if field in entry:
                            entry[field] = convert_decimal128_to_float(entry[field])
                
                # Derive payment_details from the latest payment_status entry
                payment_details = payment_status[-1] if payment_status else {
                    'status': 'Not Paid',
                    'amount_paid': 0.0,
                    'pending_amount': convert_decimal128_to_float(getattr(obj, 'total_amount', 0.0)),
                    'payment_method': None,
                    'payment_details': None,
                    'paid_by': None
                }
                
                # Get total_amount_paid and calculate pending_amount
                total_amount_paid = convert_decimal128_to_float(getattr(obj, 'total_amount_paid', 0))
                total_amount = convert_decimal128_to_float(getattr(obj, 'total_amount', 0))
                pending_amount = max(0.0, total_amount - total_amount_paid)
                
                # Build item data
                item_data = {
                    'id': str(getattr(obj, '_id', None)),
                    'grn_number': getattr(obj, 'grn_number', None),
                    'vendor_id': getattr(obj, 'vendor_id', None),
                    'vendor': vendor_details['vendor'],
                    'contact_person': vendor_details['contact_person'],
                    'phone': vendor_details['phone'],
                    'address': vendor_details['address'],
                    'is_active': getattr(obj, 'is_active', None),
                    'payment_status': payment_status,
                    'payment_details': payment_details,
                    'total_amount_paid': total_amount_paid,
                    'pending_amount': pending_amount,
                    'purchase_category': getattr(obj, 'purchase_category', None),
                    'invoice_no': getattr(obj, 'invoice_no', None),
                    'credit_period': getattr(obj, 'credit_period', None) or '',
                    'payment_mode': getattr(obj, 'payment_mode', None),
                    'remarks': getattr(obj, 'remarks', None) or '',
                    'created_by': getattr(obj, 'created_by', None),
                    "items":getattr(obj, 'items', None),
                    'lastmodified_by': getattr(obj, 'lastmodified_by', None)
                }
                
                # Handle date fields
                date_fields = ['date', 'invoice_date', 'due_date', 'created_date', 'lastmodified_date']
                for field in date_fields:
                    value = getattr(obj, field, None)
                    item_data[field] = value.isoformat() if hasattr(value, 'isoformat') else str(value) if value else None
                
                # Handle numeric fields
                numeric_fields = [
                    'non_taxable_amount', 'taxable_amount', 'tax_paid_to_supplier',
                    'local_tax', 'cgst', 'sgst', 'igst', 'cess', 'central_sales_tax',
                    'round_amount', 'total_amount', 'tax_on_free_items', 'total_discount',
                    'net_invoice_amount', 'quotation_rate', 'courier_transport_charge'
                ]
                for field in numeric_fields:
                    value = getattr(obj, field, None)
                    item_data[field] = convert_decimal128_to_float(value)
                
                response_data.append(item_data)
                
            except Exception as item_error:
                logger.error(f"Error processing TravellersIN {obj.grn_number}: {str(item_error)}\n{traceback.format_exc()}")
                response_data.append({
                    'id': str(getattr(obj, '_id', None)),
                    'grn_number': getattr(obj, 'grn_number', None),
                    'vendor_id': getattr(obj, 'vendor_id', None),
                    'vendor': '',
                    'contact_person': '',
                    'phone': '',
                    'address': '',
                    'is_active': getattr(obj, 'is_active', None),
                    'error': f'Processing failed: {str(item_error)}'
                })
        
        return Response({
            'status': 'success',
            'data': response_data,
            'pagination': {
                'current_page': page,
                'total_pages': total_pages,
                'total_records': total_records,
                'has_next': page < total_pages,
                'has_previous': page > 1
            }
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.error(f"Error in get_travellers_in_list: {str(e)}\n{traceback.format_exc()}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def delete_grn_record(request):
    """
    Soft delete a GRN record by setting is_active to False
    """
    grn_number = request.query_params.get('grn_number')
    if not grn_number:
        return Response({
            'status': 'error',
            'message': 'Missing grn_number in query parameters'
        }, status=400)

    grn_number = urllib.parse.unquote(grn_number).strip()
    print(f"Attempting to soft delete GRN: '{grn_number}'")

    try:
        # Connect to MongoDB
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db["travellers_in"]

        # Perform the update
        result = collection.update_one(
            {"grn_number": grn_number, "is_active": True},
            {
                "$set": {
                    "is_active": False,
                    "lastmodified_date": timezone.now()
                }
            }
        )

        if result.modified_count == 1:
            print(f"✅ GRN {grn_number} marked as inactive.")
            return Response({
                'status': 'success',
                'message': f'GRN {grn_number} deleted successfully'
            })
        else:
            return Response({
                'status': 'error',
                'message': f'No active GRN found with number: {grn_number}'
            }, status=404)

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error deleting GRN {grn_number}: {str(e)}\n{error_details}")
        return Response({
            'status': 'error',
            'message': f'Error deleting GRN: {str(e)}',
            'trace': error_details
        }, status=500)

@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def update_payment_status(request):
    grn_number = request.query_params.get('grn_number')
    employee_id = request.data.get('auth-user-id')
    if not grn_number:
        return Response({
            'status': 'error',
            'message': 'Missing grn_number in query parameters'
        }, status=400)

    grn_number = urllib.parse.unquote(grn_number).strip()
    print(f"Attempting to update payment status for GRN: '{grn_number}'")

    try:
        data = request.data
        if not isinstance(data, dict):
            return Response({
                'status': 'error',
                'message': 'Request body must be a JSON object'
            }, status=400)

        print("Request data:", data)
        
        # Updated required fields to include payment_date
        required_fields = ['amount_paid', 'payment_method', 'payment_date', 'status']
        for field in required_fields:
            if field not in data:
                return Response({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }, status=400)

        # Validate status
        if data['status'] not in ['Paid', 'Partially Paid']:
            return Response({
                'status': 'error',
                'message': 'Status must be "Paid" or "Partially Paid"'
            }, status=400)

        # Validate amount_paid
        try:
            amount_paid = float(data['amount_paid'])
            if amount_paid < 0:
                return Response({
                    'status': 'error',
                    'message': 'Amount paid cannot be negative'
                }, status=400)
        except (ValueError, TypeError):
            return Response({
                'status': 'error',
                'message': 'Invalid amount_paid value'
            }, status=400)

        # Validate payment_date (dd/mm/yyyy format)
        try:
            payment_date = data['payment_date']
            from datetime import datetime
            # Parse dd/mm/yyyy format
            parsed_date = datetime.strptime(payment_date, '%d/%m/%Y')
        except (ValueError, TypeError):
            return Response({
                'status': 'error',
                'message': 'Invalid payment_date format. Expected DD/MM/YYYY format'
            }, status=400)

        # Create payment entry with payment_date
        payment_entry = {
            'status': data['status'],
            'amount_paid': amount_paid,
            'payment_method': data['payment_method'],
            'payment_details': data.get('payment_details'),
            'payment_date': payment_date,  # Add payment_date to entry
            'paid_by': employee_id,
            'timestamp': timezone.now().isoformat()
        }

        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db["travellers_in"]

        # Get current document
        current_doc = collection.find_one({"grn_number": grn_number, "is_active": True})
        if not current_doc:
            return Response({
                'status': 'error',
                'message': f'No active record found for GRN {grn_number}'
            }, status=404)

        # Get current payment_status
        current_status = current_doc.get('payment_status', [])
        if isinstance(current_status, str):
            try:
                current_status = json.loads(current_status)
                if not isinstance(current_status, list):
                    current_status = []
            except json.JSONDecodeError:
                current_status = []
        elif not isinstance(current_status, list):
            current_status = []

        # Get current total_amount_paid
        current_total_paid = convert_decimal128_to_float(current_doc.get('total_amount_paid', 0))

        # Calculate new total_amount_paid
        new_total_paid = current_total_paid + amount_paid

        # Calculate pending_amount
        total_amount = convert_decimal128_to_float(current_doc.get('total_amount', 0))
        pending_amount = max(0.0, total_amount - new_total_paid)

        # Update payment entry with pending_amount
        payment_entry['pending_amount'] = pending_amount

        # Validate status consistency
        if data['status'] == 'Paid' and pending_amount > 0:
            return Response({
                'status': 'error',
                'message': 'Status cannot be "Paid" when pending amount is greater than 0'
            }, status=400)
        if data['status'] == 'Partially Paid' and pending_amount <= 0:
            return Response({
                'status': 'error',
                'message': 'Status cannot be "Partially Paid" when pending amount is 0'
            }, status=400)

        # Append new payment entry
        new_status = current_status + [payment_entry]

        # Update document
        update_data = {
            "payment_status": json.dumps(new_status),
            "total_amount_paid": Decimal128(str(new_total_paid)),
            "lastmodified_date": timezone.now()
        }

        result = collection.update_one(
            {"grn_number": grn_number, "is_active": True},
            {"$set": update_data}
        )

        if result.modified_count == 1:
            return Response({
                'status': 'success',
                'message': f'Payment status updated for GRN {grn_number}',
                'payment_status': new_status,
                'data': {
                    'total_amount_paid': new_total_paid,
                    'pending_amount': pending_amount,
                    'payment_method': payment_entry['payment_method'],
                    'payment_details': payment_entry['payment_details'],
                    'payment_date': payment_entry['payment_date'],
                    'paid_by': employee_id,
                    'timestamp': payment_entry['timestamp']
                }
            })
        else:
            return Response({
                'status': 'error',
                'message': f'Failed to update record for GRN {grn_number}'
            }, status=500)

    except ValueError as ve:
        return Response({
            'status': 'error',
            'message': f'Invalid numeric value: {str(ve)}'
        }, status=400)
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Error updating MongoDB: {str(e)}\n{error_details}")
        return Response({
            'status': 'error',
            'message': f'Failed to update payment status: {str(e)}',
            'trace': error_details
        }, status=500)
    
def convert_decimal128_to_float(value):
    """Convert Decimal128 or other numeric types to float safely"""
    if value is None:
        return 0.0
    if isinstance(value, Decimal128):
        return float(value.to_decimal())
    elif isinstance(value, (int, float)):
        return float(value)
    elif isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    else:
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

def clean_mongo_document(doc):
    """Convert Decimal128 and ObjectId to JSON-safe types"""
    if isinstance(doc, dict):
        return {k: clean_mongo_document(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [clean_mongo_document(i) for i in doc]
    elif isinstance(doc, Decimal128):
        return float(doc.to_decimal())
    elif isinstance(doc, ObjectId):
        return str(doc)
    return doc

@api_view(['GET'])
@permission_classes([HasRolePermission])
def travellers_in_detail(request, grn_number):
    """
    Retrieve a specific TravellersIN record by GRN number
    """
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db["travellers_in"]

        # Fetch the document
        document = collection.find_one({"grn_number": grn_number, "is_active": True})
        if not document:
            logger.warning(f"No active record found for GRN {grn_number}")
            return Response({
                'status': 'error',
                'message': f'No active record found for GRN {grn_number}'
            }, status=status.HTTP_404_NOT_FOUND)

        # Ensure 'items' is always a list
        if isinstance(document.get('items'), str):
            try:
                document['items'] = json.loads(document['items'])
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in items for GRN {grn_number}")
                document['items'] = []
        elif not document.get('items'):
            document['items'] = []

        # Ensure 'payment_status' is always a list
        if isinstance(document.get('payment_status'), str):
            try:
                document['payment_status'] = json.loads(document['payment_status'])
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in payment_status for GRN {grn_number}")
                document['payment_status'] = []
        elif not document.get('payment_status'):
            document['payment_status'] = []

        # Clean Mongo document
        cleaned_doc = clean_mongo_document(document)

        # Convert numeric fields in items
        for item in cleaned_doc.get('items', []):
            numeric_item_fields = [
                'itemValue', 'packingPrice', 'unitPrice', 'cgstAmt', 'sgstAmt',
                'purchaseCost', 'mrp', 'tax', 'cgstPercent', 'sgstPercent',
                'purchaseDiscountPercent', 'discountedAmt', 'packing', 'quantity',
                'free', 'totalstock'
            ]
            for field in numeric_item_fields:
                if field in item:
                    item[field] = convert_decimal128_to_float(item[field])

        # Convert numeric fields in payment_status
        for entry in cleaned_doc.get('payment_status', []):
            numeric_payment_fields = ['amount_paid', 'pending_amount']
            for field in numeric_payment_fields:
                if field in entry:
                    entry[field] = convert_decimal128_to_float(entry[field])

        # Fetch vendor details safely
        vendor_details = {
            'vendor': '',
            'contact_person': '',
            'phone': '',
            'address': '',
            'email': ''
        }

        vendor_id = cleaned_doc.get('vendor_id')
        if vendor_id:
            try:
                vendor = Vendors.objects.get(vendor_id=vendor_id)
                vendor_details = {
                    'vendor': getattr(vendor, 'name', ''),
                    'contact_person': getattr(vendor, 'contactPerson', '') or '',
                    'phone': getattr(vendor, 'Phone', '') or '',
                    'address': f"{getattr(vendor, 'addressLine1', '')}, {getattr(vendor, 'addressLine2', '')}".strip(', '),
                    'email': getattr(vendor, 'email', '') or ''
                }
            except Vendors.DoesNotExist:
                logger.warning(f"Vendor with vendor_id {vendor_id} not found")

        # Add vendor details to response
        cleaned_doc.update(vendor_details)

        return Response({
            'status': 'success',
            'data': cleaned_doc
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in travellers_in_detail for GRN {grn_number}: {str(e)}\n{traceback.format_exc()}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
from datetime import date, datetime

def normalize_dates(data):
    """Convert date/datetime objects into ISO strings recursively"""
    for key, value in data.items():
        if isinstance(value, date) and not isinstance(value, datetime):
            data[key] = value.isoformat()   # YYYY-MM-DD
        elif isinstance(value, datetime):
            data[key] = value.isoformat()   # full timestamp
        elif isinstance(value, dict):
            normalize_dates(value)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                if isinstance(v, (date, datetime)):
                    data[key][i] = v.isoformat()
                elif isinstance(v, dict):
                    normalize_dates(v)
    return data

@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def travellers_in_update(request, grn_number):
    """
    Update an existing TravellersIN record by GRN number
    """
    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db["travellers_in"]

        # Fetch the existing document
        document = collection.find_one({"grn_number": grn_number, "is_active": True})
        if not document:
            logger.warning(f"No active record found for GRN {grn_number}")
            return Response({
                'status': 'error',
                'message': f'No active record found for GRN {grn_number}'
            }, status=status.HTTP_404_NOT_FOUND)

        data = request.data

        # Map frontend field names to backend field names
        mapped_data = {
            'purchase_category': data.get('purchaseCategory'),
            'vendor_id': data.get('vendor_id'),
            'date': data.get('date'),
            'invoice_no': data.get('invoiceNo'),
            'invoice_date': data.get('invoiceDate'),
            'credit_period': data.get('creditPeriod', ''),
            'due_date': data.get('dueDate'),
            'payment_mode': data.get('paymentMode'),
            'items': json.dumps(data.get('items', [])),  # Store as JSON string
            'lastmodified_date': timezone.now().isoformat(),  # ✅ ensure ISO string
            'lastmodified_by': data.get('auth-user-id', 'Anonymous')
        }

        # Map summary fields
        summary = data.get('summary', {})
        summary_mapping = {
            'non_taxable_amount': 'nonTaxableAmount',
            'taxable_amount': 'taxableAmount',
            'tax_paid_to_supplier': 'taxPaidToSupplier',
            'local_tax': 'localTax',
            'remarks': 'remarks',
            'cgst': 'cgst',
            'sgst': 'sgst',
            'igst': 'igst',
            'cess': 'cess',
            'central_sales_tax': 'centralSalesTax',
            'round_amount': 'roundAmount',
            'total_amount': 'totalAmount',
            'tax_on_free_items': 'taxOnFreeItems',
            'total_discount': 'totalDiscount',
            'net_invoice_amount': 'netInvoiceAmount',
            'quotation_rate': 'quotationRate',
            'courier_transport_charge': 'courierTransportCharge',
        }

        for backend_field, frontend_field in summary_mapping.items():
            value = summary.get(frontend_field, document.get(backend_field, 0))
            mapped_data[backend_field] = convert_decimal128_to_float(value)

        # Validate and serialize data
        serializer = TravellersINSerializer(data=mapped_data, partial=True)
        if serializer.is_valid():
            update_data = serializer.validated_data

            # ✅ normalize all dates before saving
            update_data = normalize_dates(update_data)

            # Convert numeric fields to Decimal128 for MongoDB
            numeric_fields = [
                'non_taxable_amount', 'taxable_amount', 'tax_paid_to_supplier',
                'local_tax', 'cgst', 'sgst', 'igst', 'cess', 'central_sales_tax',
                'round_amount', 'total_amount', 'tax_on_free_items', 'total_discount',
                'net_invoice_amount', 'quotation_rate', 'courier_transport_charge'
            ]
            for field in numeric_fields:
                if field in update_data:
                    update_data[field] = Decimal128(str(update_data[field]))

            # Perform the update
            result = collection.update_one(
                {"grn_number": grn_number, "is_active": True},
                {"$set": update_data}
            )

            if result.modified_count == 1:
                updated_doc = collection.find_one({"grn_number": grn_number, "is_active": True})
                cleaned_doc = clean_mongo_document(updated_doc)

                # (rest of your post-processing unchanged...)

                return Response({
                    'status': 'success',
                    'message': f'TravellersIN record {grn_number} updated successfully',
                    'data': cleaned_doc
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'status': 'error',
                    'message': f'Failed to update record for GRN {grn_number}'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            logger.warning(f"Validation failed for GRN {grn_number}: {serializer.errors}")
            return Response({
                'status': 'error',
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error(f"Error in travellers_in_update for GRN {grn_number}: {str(e)}\n{traceback.format_exc()}")
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

from rest_framework.decorators import api_view
from rest_framework.response import Response
from pymongo import MongoClient
from bson.decimal128 import Decimal128
from bson.objectid import ObjectId
from django.conf import settings
import json

# Recursive cleaner to convert Decimal128 & ObjectId to JSON-safe types
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

def convert_decimal128_to_float(value):
    if isinstance(value, Decimal128):
        return float(value.to_decimal())
    try:
        return float(value)
    except Exception:
        return value

@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_previous_purchases(request):
    hsn = request.GET.get('hsn')
    item_name = request.GET.get('item_name')

    if not hsn or not item_name:
        return Response({'status': 'error', 'message': 'HSN and Item Name are required'}, status=400)

    try:
        client = MongoClient(mongo_uri)
        db = client[db_name]
        purchases_collection = db["travellers_in"]
        vendors_collection = db["vendors"]

        # Fetch active purchase records
        documents = purchases_collection.find({"is_active": True})
        matched_purchases = []

        for doc in documents:
            # Handle items field
            items = doc.get('items', [])
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except json.JSONDecodeError as e:
                    print(f"Error parsing items for GRN {doc.get('grn_number')}: {e}")
                    continue
            elif not isinstance(items, list):
                continue

            # Handle payment_details field
            payment_details = doc.get('payment_details', {})
            if isinstance(payment_details, str):
                try:
                    payment_details = json.loads(payment_details)
                except json.JSONDecodeError:
                    payment_details = {}
            if not isinstance(payment_details, dict):
                payment_details = {}
            else:
                numeric_fields = ['amount_paid', 'pending_amount']
                for field in numeric_fields:
                    if field in payment_details:
                        payment_details[field] = convert_decimal128_to_float(payment_details[field])

            # Match item based on HSN + name (normalize spaces and case)
            for item in items:
                mongo_name = " ".join(item.get('name', '').strip().split())
                input_name = " ".join(item_name.strip().split())

                if item.get('hsn', '').strip() == hsn.strip() and mongo_name.lower() == input_name.lower():
                    doc['matched_item'] = item
                    doc['payment_details'] = payment_details

                    # Fetch vendor name using vendor_id
                    vendor_name = None
                    vendor_id = doc.get('vendor_id')
                    if vendor_id:
                        vendor_doc = vendors_collection.find_one({
                            "$and": [
                                {"is_active": True},
                                {"$or": [
                                    {"vendor_id": str(vendor_id).strip()},
                                    {"vendor_id": int(vendor_id)}
                                ]}
                            ]
                        })
                        if vendor_doc:
                            vendor_name = vendor_doc.get('name')
                    doc['vendor_name'] = vendor_name

                    cleaned_doc = clean_mongo_document(doc)
                    matched_purchases.append(cleaned_doc)
                    break  # stop scanning this document once a match is found

        return Response({'status': 'success', 'data': matched_purchases}, status=200)

    except Exception as e:
        print(f"Error in get_previous_purchases: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=500)

import traceback
db = get_database()
purchases_collection = db.travellers_in
intents_collection = db.traveller_intent
items_collection = db["items"]
@api_view(['GET'])
@permission_classes([HasRolePermission])
def travellers_stock(request):
    item_name = request.GET.get("itemName")
    hsn_number = request.GET.get("hsn")
    try:
        # :small_blue_diamond: Fetch from items collection instead of purchases
        query = {"is_active": True}
        if item_name:
            query["itemName"] = item_name.strip()
        if hsn_number:
            query["hsn"] = hsn_number.strip()
        item_doc = items_collection.find_one(query)
        if not item_doc:
            return JsonResponse({"success": False, "error": "Item not found"}, status=404)
        total_quantity = int(item_doc.get("total_quantity", 0) or 0)
        approved_quantity = int(item_doc.get("approved_quantity", 0) or 0)
        available_stock = total_quantity - approved_quantity
        return JsonResponse({
            "success": True,
            "itemName": item_doc.get("itemName"),
            "hsn": item_doc.get("hsn"),
            "total_quantity": total_quantity,
            "approved_quantity": approved_quantity,
            "total_stock": available_stock
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

# -------------------------------------------------------------------
# Traveller Intent CRUD
# -------------------------------------------------------------------
@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([HasRolePermission])
def travellers_intent(request):
    if request.method == 'GET':
        items = TravellerIntent.objects.all()
        serializer = TravellerIntentSerializer(items, many=True)
        return Response(serializer.data)
    elif request.method == 'POST':
        # Parse date
        intent_date_str = request.data.get('date')
        if intent_date_str:
            try:
                intent_date = datetime.strptime(intent_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Invalid date format. Expected YYYY-MM-DD.'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            intent_date = date.today()

        # Determine financial year prefix
        if intent_date.month >= 4:
            financial_year_start = intent_date.year
        else:
            financial_year_start = intent_date.year - 1
        year_suffix = str(financial_year_start)[-2:]
        prefix = f"IN0{year_suffix}/"

        # Generate new intent number
        last_intent = (
            TravellerIntent.objects.filter(intent_number__startswith=prefix)
            .order_by('-intent_number')
            .first()
        )
        if last_intent and last_intent.intent_number:
            last_number = int(last_intent.intent_number.split('/')[-1])
        else:
            last_number = 0
        new_intent_number = f"{prefix}{last_number + 1:05d}"  # e.g., IN25/00001

        # Add intent number + created_by
        data = request.data.copy()
        data['intent_number'] = new_intent_number
        auth_user_id = request.data.get("auth-user-id")
        data['created_by'] = auth_user_id

        serializer = TravellerIntentSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            print("Serializer errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'PATCH':
        intent_id = request.data.get("intent_id")
        item_id = request.data.get("item_id")

        if not intent_id or not item_id:
            return Response({"error": "intent_id and item_id required"}, status=400)

        try:
            intent = TravellerIntent.objects.get(id=intent_id)
        except TravellerIntent.DoesNotExist:
            return Response({"error": "Intent not found"}, status=404)

        # items are stored as JSON string, so parse them
        items = intent.items
        if isinstance(items, str):
            try:
                items = json.loads(items)
            except json.JSONDecodeError:
                return Response({"error": "Invalid items format"}, status=400)

        updated_items = []
        for item in items:
            if str(item.get("item_id")) == str(item_id):
                old_approved = int(item.get("approved", 0))
                new_approved = int(request.data.get("approved", 0) or 0)

                delta = new_approved - old_approved

                # 🔥 reduce stock only for delta (newly approved qty)
                if delta > 0:
                    item_name = item.get("itemName")
                    hsn = item.get("hsn")
                    success = reduce_stock(item_name, hsn, delta,auth_user_id)
                    if not success:
                        return Response({"error": "Insufficient stock"}, status=400)

                # update item fields
                item["approved"] = new_approved
                item["status"] = request.data.get("status", item.get("status"))
            updated_items.append(item)

        # save back to intent
        intent.items = json.dumps(items)
        intent.save()

        return Response({"success": True, "message": "Intent updated"})



# -------------------------------------------------------------------
# Items List (for dropdowns)
# -------------------------------------------------------------------
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from pymongo import MongoClient

@api_view(['GET'])
@permission_classes([HasRolePermission])
def items_list(request):
    """
    Return list of all active items with id, itemName, and hsn
    using PyMongo directly (Djongo-free).
    """
    try:
        # Connect to MongoDB
        client = MongoClient("mongodb://localhost:27017/")  # adjust URI if needed
        db = client['StoreTrust']  # replace with your DB name
        items_collection = db['items']

        # Ensure all documents have is_active
        items_collection.update_many(
            {"is_active": {"$exists": False}},
            {"$set": {"is_active": True}}
        )

        # Fetch active items
        active_items = list(items_collection.find(
            {"is_active": True},
            {"_id": 1, "itemName": 1, "hsn": 1}
        ))

        # Convert ObjectId to string for JSON
        for item in active_items:
            item["id"] = str(item["_id"])
            del item["_id"]

        return Response(active_items, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": "Server error occurred", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# @api_view(['GET'])
# def items_list(request):
#     """
#     Return list of all items with id, itemName, and hsn
#     """
#     items = Items.objects.all().values("id", "itemName", "hsn")
#     return Response(list(items), status=status.HTTP_200_OK)
def reduce_stock(item_name, hsn, quantity_to_increment, auth_user_id):
    """
    Increment approved_quantity for a given item HSN in the items collection.
    - item_name: name of the item (for logging)
    - hsn: HSN code
    - quantity_to_increment: int (positive value)
    - auth_user_id: ID of user making the change
    """
    if not hsn or quantity_to_increment <= 0:
        print(f"[reduce_stock] Skipping {item_name} (HSN {hsn}), qty {quantity_to_increment}")
        return False
    items_collection = db["items"]
    try:
        result = items_collection.find_one_and_update(
            {"hsn": str(hsn).strip(), "is_active": True},
            {
                "$inc": {"approved_quantity": quantity_to_increment},
                "$set": {
                    "lastmodified_date": datetime.utcnow(),
                    "lastmodified_by": auth_user_id
                }
            },
            return_document=True
        )
        if not result:
            print(f"[reduce_stock] No item found for HSN {hsn}, approved_quantity not updated.")
            return False
        print(f"[reduce_stock] {item_name} (HSN {hsn}): approved_quantity +{quantity_to_increment}")
        return True
    except Exception as e:
        print(f"[reduce_stock] Error updating HSN {hsn}: {str(e)}")
        return False


# def restore_stock(item_name, hsn, quantity_to_restore, auth_user_id):
#     """
#     Restore stock across active travellers_in records for the specified item.
#     Returns True if successful, False if insufficient records or other errors.
#     """
#     if quantity_to_restore <= 0:
#         logger.debug(f"[restore_stock] No stock restoration needed: quantity={quantity_to_restore}")
#         return True

#     logger.debug(f"[restore_stock] Restoring {quantity_to_restore} stock for item: '{item_name}', hsn: '{hsn}'")

#     item_name = item_name.strip().lower()
#     safe_hsn = str(hsn or "").strip()

#     # Fetch active purchases, sorted by created_date (FIFO)
#     purchases = list(purchases_collection.find({"is_active": True}).sort("created_date", 1))
    
#     total_restored = 0
#     updates = []

#     for purchase in purchases:
#         if total_restored >= quantity_to_restore:
#             break

#         items = purchase.get("items", [])
#         if isinstance(items, str):
#             try:
#                 items = json.loads(items)
#             except json.JSONDecodeError:
#                 logger.error(f"[restore_stock] Invalid JSON in items for purchase {purchase['_id']}")
#                 continue

#         for idx, item in enumerate(items):
#             item_name_match = (
#                 (item.get("itemName", "").strip().lower() == item_name) or 
#                 (item.get("name", "").strip().lower() == item_name)
#             )
#             item_hsn = str(item.get("hsn", "")).strip()
#             hsn_match = item_hsn == safe_hsn or (not item_hsn and not safe_hsn)

#             if item_name_match and hsn_match:
#                 current_stock = int(item.get("totalstock", 0))
#                 remaining_to_restore = quantity_to_restore - total_restored
#                 restore_qty = min(remaining_to_restore, quantity_to_restore)  # Restore up to what's needed
#                 items[idx]["totalstock"] = str(current_stock + restore_qty)
#                 total_restored += restore_qty

#                 # Store update details
#                 updates.append({
#                     "purchase_id": purchase["_id"],
#                     "items": items,
#                     "restore_qty": restore_qty
#                 })

#                 if total_restored >= quantity_to_restore:
#                     break

#     if total_restored < quantity_to_restore:
#         logger.error(f"[restore_stock] Insufficient records to restore {quantity_to_restore} stock: restored {total_restored}")
#         return False

#     # Apply updates to the database
#     for update in updates:
#         try:
#             result = purchases_collection.update_one(
#                 {"_id": update["purchase_id"], "is_active": True},
#                 {
#                     "$set": {
#                         "items": json.dumps(update["items"]),
#                         "lastmodified_by": auth_user_id,
#                         "lastmodified_at": datetime.utcnow(),
#                         "lastmodified_date": datetime.utcnow()
#                     }
#                 }
#             )
#             if result.modified_count == 0:
#                 logger.error(f"[restore_stock] Failed to update purchase {update['purchase_id']}: No documents matched")
#                 return False
#             logger.debug(f"[restore_stock] Restored {update['restore_qty']} stock to purchase {update['purchase_id']}")
#         except Exception as e:
#             logger.error(f"[restore_stock] Error updating purchase {update['purchase_id']}: {str(e)}")
#             return False

#     logger.debug(f"[restore_stock] Successfully restored {total_restored} stock")
#     return True

@api_view(["PATCH"])
@permission_classes([HasRolePermission])
def add_back_traveller_stock(request,item_name, hsn, quantity_to_decrement, auth_user_id):
    """
    Increment approved_quantity for a given item HSN in the items collection.
    - item_name: name of the item (for logging)
    - hsn: HSN code
    - quantity_to_increment: int (positive value)
    - auth_user_id: ID of user making the change
    """
    quantity_to_decrement = quantity_to_decrement* -1
    if not hsn or quantity_to_decrement >= 0:
        print(f"[reduce_stock] Skipping {item_name} (HSN {hsn}), qty {quantity_to_decrement}")
        return False
    items_collection = db["items"]
    try:
        result = items_collection.find_one_and_update(
            {"hsn": str(hsn).strip(), "is_active": True},
            {
                "$inc": {"approved_quantity": quantity_to_decrement},
                "$set": {
                    "lastmodified_date": datetime.utcnow(),
                    "lastmodified_by": auth_user_id
                }
            },
            return_document=True
        )
        if not result:
            print(f"[reduce_stock] No item found for HSN {hsn}, approved_quantity not updated.")
            return False
        print(f"[reduce_stock] {item_name} (HSN {hsn}): approved_quantity +{quantity_to_decrement}")
        return True
    except Exception as e:
        print(f"[reduce_stock] Error updating HSN {hsn}: {str(e)}")
        return False

# @api_view(["PATCH"])
# @permission_classes([HasRolePermission])
# def add_stock(request):
#     """
#     Add back stock for a specific item in travellers_in (MongoDB)
#     """
#     item_name = request.data.get("itemName")
#     hsn = request.data.get("hsn", "")
#     quantity_to_add = int(request.data.get("quantity", 0))
#     employee_id = request.data.get("auth-user-id")

#     if not item_name or quantity_to_add <= 0:
#         return Response({"error": "itemName and positive quantity are required"}, status=400)

#     purchases = list(purchases_collection.find({"is_active": True}).sort("created_date", -1))

#     for purchase in purchases:
#         items = purchase.get("items", [])
#         if isinstance(items, str):
#             try:
#                 items = json.loads(items)
#             except json.JSONDecodeError:
#                 continue

#         items_updated = False
#         for item in items:
#             item_name_match = (item.get("name", "").strip().lower() == item_name.strip().lower())
#             item_hsn = str(item.get("hsn", "")).strip()
#             hsn_match = item_hsn == hsn or (not item_hsn and not hsn)

#             if item_name_match and hsn_match:
#                 current_stock = int(item.get("totalstock", 0))
#                 item["totalstock"] = str(current_stock + quantity_to_add)
#                 items_updated = True
#                 break

#         if items_updated:
#             try:
#                 purchases_collection.update_one(
#                     {"_id": purchase["_id"]},
#                     {"$set": {
#                         "items": json.dumps(items),
#                         "lastmodified_by": employee_id,
#                         "lastmodified_at": datetime.utcnow()
#                     }}
#                 )
#                 return Response({
#                     "success": True,
#                     "itemName": item_name,
#                     "hsn": hsn,
#                     "quantity_added": quantity_to_add
#                 }, status=200)
#             except Exception as e:
#                 return Response({"error": f"Failed to update purchase: {e}"}, status=500)

#     return Response({"error": "Item not found in any active purchase"}, status=404)


def add_back_stock(item_name: str, hsn: str, quantity_to_subtract: int, employee_id: str | None = None) -> bool:
    """
    Subtract quantity from approved_quantity in items_collection.
    Finds the item by name and HSN, subtracts the quantity, and returns True if successful.
    """
    try:
        if not item_name or int(quantity_to_subtract) <= 0:
            return False
        safe_hsn = str(hsn or "").strip()
        query = {"itemName": {"$regex": f"^{item_name.strip()}$", "$options": "i"}}
        if safe_hsn:
            query["hsn"] = safe_hsn
        else:
            query["hsn"] = {"$in": [None, ""]}
        # Find the first matching item
        item_doc = items_collection.find_one(query)
        if not item_doc:
            return False
        current_approved = int(item_doc.get("approved_quantity", 0))
        new_approved = max(0, current_approved - int(quantity_to_subtract))  # prevent negative
        items_collection.update_one(
            {"_id": item_doc["_id"]},
            {"$set": {
                "approved_quantity": new_approved,
                "lastmodified_by": employee_id,
                "lastmodified_date": datetime.utcnow()
            }}
        )
        return True
    except Exception:
        # Silent failure
        return False



@api_view(["PATCH"])
@permission_classes([HasRolePermission])
def update_intent_item(request):
    intent_number = request.data.get("intent_number")
    date_str = request.data.get("date")
    items_updates = request.data.get("items", [])
    employee_id = request.data.get("auth-user-id")
    print("auth_user_id:", employee_id)

    if not all([intent_number, date_str, items_updates]):
        return Response(
            {"error": "intent_number, date, and items are required."}, status=400
        )

    try:
        intent = TravellerIntent.objects.get(
            intent_number=intent_number,
            date=parse_date(date_str)
        )
    except TravellerIntent.DoesNotExist:
        return Response({"error": "Intent not found"}, status=404)
    
    items = intent.items 
    if isinstance(items, str):
        items = json.loads(items)

    total_stock_reduced = 0
    restored_quantities = []  # Track what we're restoring

    for update in items_updates:
        item_id = update.get("item_id")
        new_status = update.get("status")
        new_quantity = update.get("quantity")
        new_item_name = update.get("itemName")
        approved_qty = update.get("approved_qty", None)
        hsn = update.get("hsn", "")

        for item in items:
            if item.get("item_id") == item_id:
                previous_approved = int(item.get("approved") or 0)
                print(f"Processing item {item_id}: previous_approved={previous_approved}, new_status={new_status}")

                # Update editable fields first
                if new_item_name is not None:
                    item["itemName"] = new_item_name

                if new_quantity is not None:
                    item["quantity"] = int(new_quantity)

                if new_status is not None:
                    item["status"] = new_status

                # Handle stock changes based on status
                stock_to_reduce = 0
                
                # FIXED: Use correct status values that match your frontend
                if new_status in ["Approve", "Partially Approve"]:
                    if approved_qty is not None:
                        new_approved = int(approved_qty)
                    else:
                        new_approved = int(item.get("quantity") or 0)
                    
                    item["approved"] = new_approved
                    item["approved_by"] = employee_id 
                    stock_to_reduce = new_approved - previous_approved
                    print(f"Approve case: new_approved={new_approved}, stock_to_reduce={stock_to_reduce}")
                
                # FIXED: Handle both "Reject" and "Rejected" for compatibility
                elif new_status in ["Reject", "Rejected", "Pending"]:
                    # When rejecting, we need to restore all previously approved stock
                    item["approved"] = 0  # CRITICAL: Set approved to 0
                    item["approved_by"] = "Pending" if new_status == "Pending" else employee_id
                    stock_to_reduce = 0 - previous_approved  # This will be negative, meaning restore
                    restore_amount = abs(stock_to_reduce)
                    
                    if restore_amount > 0:
                        restored_quantities.append({
                            'item_name': item.get("itemName"),
                            'hsn': str(item.get("hsn", "")),
                            'quantity': restore_amount
                        })
                    
                    print(f"Reject/Pending case: setting approved=0, stock_to_reduce={stock_to_reduce} (restore {restore_amount})")
                
                # FIXED: Handle stock operations - moved outside the if-elif blocks
                if stock_to_reduce > 0:
                    # Reduce stock (for approvals)
                    print(f"Reducing stock by {stock_to_reduce} for item {item.get('itemName')}")
                    reduce_success = reduce_stock(
                        item.get("itemName"),
                        str(item.get("hsn", "")),
                        stock_to_reduce,
                        employee_id
                    )
                    if not reduce_success:
                        return Response(
                            {"error": f"Insufficient stock to approve {item.get('itemName')}."},
                            status=400
                        )
                    total_stock_reduced += stock_to_reduce

                elif stock_to_reduce < 0:
                    # Restore stock (for rejections/cancellations)
                    restore_amount = abs(stock_to_reduce)
                    print(f"Restoring stock by {restore_amount} for item {item.get('itemName')}")
                    
                    # Use the existing add_back_stock utility function
                    restore_success = add_back_stock(
                        item.get("itemName"),
                        str(item.get("hsn", "")),
                        restore_amount,
                        employee_id
                    )
                    
                    if not restore_success:
                        return Response(
                            {"error": f"Failed to restore stock for {item.get('itemName')}."},
                            status=400
                        )
                    print(f"Successfully restored {restore_amount} stock for {item.get('itemName')}")

                break  # Item found and processed, move to next update

    # FIXED: Recalculate total approved qty at intent level - use correct status values
    total_approved_qty = sum(
        int(i.get("approved", 0) or 0) for i in items 
        if i.get("status") in ["Approve", "Partially Approve"]  # Only count approved items
    )
    print(f"Recalculated total_approved_qty: {total_approved_qty}")

    # Save TravellerIntent
    intent.items = json.dumps(items)  # Ensure serialization
    intent.approved_qty = total_approved_qty
    intent.lastmodified_by = str(employee_id)
    intent.lastmodified_date = timezone.now()
    intent.save()

    return Response({
        "success": True,
        "total_stock_reduced": total_stock_reduced,
        "approved_qty": total_approved_qty,
        "items": items,
        "restored_quantities": restored_quantities  # Add this for debugging
    }, status=200)

# Keep your existing restore_stock_fifo function
def restore_stock_fifo(item_name, hsn, quantity_to_restore, employee_id):
    """
    Restore stock using FIFO (First In, First Out) approach.
    Adds stock back to the oldest purchases first.
    """
    if quantity_to_restore <= 0:
        return True

    try:
        # Get purchases in ascending order (oldest first) for FIFO restoration
        purchases = list(purchases_collection.find({"is_active": True}).sort("created_date", 1))
        
        total_restored = 0
        item_name_lower = item_name.strip().lower()
        safe_hsn = str(hsn or "").strip()

        for purchase in purchases:
            if total_restored >= quantity_to_restore:
                break

            items = purchase.get("items", [])
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except json.JSONDecodeError:
                    continue

            items_updated = False
            for item in items:
                # Match by name (either 'name' or 'itemName') and HSN
                name_val = (item.get("name") or item.get("itemName") or "").strip().lower()
                if name_val == item_name_lower:
                    item_hsn = str(item.get("hsn", "")).strip()
                    hsn_match = item_hsn == safe_hsn or (not item_hsn and not safe_hsn)
                    
                    if hsn_match:
                        current_stock = int(item.get("totalstock", 0))
                        restore_qty = quantity_to_restore - total_restored
                        
                        # Add the stock back
                        item["totalstock"] = str(current_stock + restore_qty)
                        total_restored += restore_qty
                        items_updated = True
                        break

            if items_updated:
                # Update the purchase in database
                try:
                    result = purchases_collection.update_one(
                        {"_id": purchase["_id"]},
                        {
                            "$set": {
                                "items": json.dumps(items),
                                "lastmodified_by": employee_id,
                                "lastmodified_at": datetime.utcnow(),
                                "lastmodified_date": datetime.utcnow()
                            }
                        }
                    )
                    if result.modified_count == 0:
                        return False
                except Exception as e:
                    print(f"Error updating purchase: {e}")
                    return False

        return total_restored >= quantity_to_restore
        
    except Exception as e:
        print(f"Error in restore_stock_fifo: {e}")
        return False

# -------------------------------------------------------------------
# Soft Delete Intent Item
# -------------------------------------------------------------------
@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def soft_delete_intent_item(request):
    intent_number = request.query_params.get('intent_number')
    date_str = request.query_params.get('date')
    item_id = request.query_params.get('item_id')

    if not (intent_number and date_str and item_id):
        return Response({'error': 'intent_number, date, and item_id are required.'}, status=400)

    try:
        intent = TravellerIntent.objects.get(intent_number=intent_number, date=parse_date(date_str))
    except TravellerIntent.DoesNotExist:
        return Response({'error': 'Intent not found'}, status=404)

    items = json.loads(intent.items) if isinstance(intent.items, str) else intent.items
    updated = False
    for item in items:
        if str(item.get('item_id')) == str(item_id):   # 🔹 ensure string comparison
            item['is_active'] = False
            updated = True
            break

    if not updated:
        return Response({'error': 'Item not found'}, status=404)

    # Save back as JSON
    intent.items = json.dumps(items)   # 🔹 ensure serialization
    intent.lastmodified_by = request.query_params.get('auth-user-id', 'unknown user')
    intent.lastmodified_date = timezone.now()
    intent.save()

    return Response({'message': 'Item soft-deleted successfully'}, status=200)



# -------------------------------------------------------------------
# Soft Delete Intent
# -------------------------------------------------------------------
@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def soft_delete_intent(request):
    intent_number = request.query_params.get('intent_number')
    date_str = request.query_params.get('date')

    if not intent_number or not date_str:
        return Response({"success": False, "error": "Missing parameters"}, status=400)

    filter_date = parse_date(date_str)
    if not filter_date:
        return Response({"success": False, "error": "Invalid date format. Expected YYYY-MM-DD"}, status=400)

    intents = TravellerIntent.objects.filter(intent_number=intent_number, date=filter_date)

    if not intents.exists():
        return Response({"success": False, "error": "Intent not found"}, status=404)

    # ✅ Mark all matching intents as inactive
    intents.update(
        is_active=False,
        lastmodified_by=request.query_params.get('auth-user-id', 'unknown user'),
        lastmodified_date=timezone.now()
    )

    return Response({"success": True, "message": f"{intents.count()} intent(s) soft-deleted successfully"})



# -------------------------------------------------------------------
# Get Intents by Date Range
# -------------------------------------------------------------------
@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_travellers_intent_by_date_range(request):
    from_date_str = request.query_params.get('from_date')
    to_date_str = request.query_params.get('to_date')

    queryset = TravellerIntent.objects.all()

    if from_date_str:
        from_date = parse_date(from_date_str)
        if not from_date:
            return Response({'error': 'Invalid from_date format. Expected YYYY-MM-DD'}, status=400)
        queryset = queryset.filter(date__gte=from_date)

    if to_date_str:
        to_date = parse_date(to_date_str)
        if not to_date:
            return Response({'error': 'Invalid to_date format. Expected YYYY-MM-DD'}, status=400)
        queryset = queryset.filter(date__lte=to_date)

    serializer = TravellerIntentSerializer(queryset, many=True)
    return Response(serializer.data, status=200)


