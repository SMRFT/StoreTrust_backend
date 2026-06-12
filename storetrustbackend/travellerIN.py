from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
import json
from .models import TravellersIN, Vendors
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
from decimal import Decimal
from bson.decimal128 import Decimal128
from bson.objectid import ObjectId
import os, re
from dotenv import load_dotenv
import certifi
import traceback
import urllib
from datetime import date, datetime

from .models import Items
from .serializers import ItemsSerializer

logger = logging.getLogger(__name__)

load_dotenv()

# ─────────────────────────────────────────────
# Single MongoDB connection used across the entire module
# ─────────────────────────────────────────────
env_type  = os.environ.get("ENV_CLASSIFICATION", "local")
mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name   = os.environ.get("STORETRUST_DB_NAME", "StoreTrust")

_mongo_client = MongoClient(mongo_uri)
db = _mongo_client[db_name]

purchases_collection = db["travellers_in"]
intents_collection   = db["traveller_intent"]
items_collection     = db["items"]
vendors_collection   = db["vendors"]


# ─────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────

def convert_decimal128_to_float(value):
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


def normalize_dates(data):
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        elif isinstance(value, date):
            data[key] = value.isoformat()
        elif isinstance(value, dict):
            normalize_dates(value)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                if isinstance(v, (date, datetime)):
                    data[key][i] = v.isoformat()
                elif isinstance(v, dict):
                    normalize_dates(v)
    return data


# ─────────────────────────────────────────────
# Item name resolver — looks up itemName from
# the Items Django model using item_id
# ─────────────────────────────────────────────

def get_item_name_by_id(item_id):
    """
    Resolve itemName from the Items model using item_id.
    Returns the itemName string or None if not found.
    """
    if item_id is None:
        return None
    try:
        item = Items.objects.get(item_id=int(item_id))
        return item.itemName
    except Items.DoesNotExist:
        logger.warning(f"[get_item_name_by_id] No item found for item_id={item_id}")
        return None
    except Exception as e:
        logger.error(f"[get_item_name_by_id] Error looking up item_id={item_id}: {e}")
        return None


# ─────────────────────────────────────────────
# Stock helpers
# ─────────────────────────────────────────────

def update_stock_by_hsn(items):
    """Increment total_quantity in items collection for each HSN in the list."""
    for item in items:
        hsn = item.get("hsn")
        qty = int(item.get("totalstock", 0))
        if hsn and qty > 0:
            result = items_collection.find_one_and_update(
                {"hsn": hsn},
                {"$inc": {"total_quantity": qty}},
                return_document=True,
            )
            if not result:
                logger.warning(f"No item found for HSN {hsn}, stock not updated.")


def reduce_stock(item_name, hsn, quantity_to_increment, auth_user_id):
    if not item_name or quantity_to_increment <= 0:
        logger.debug(f"[reduce_stock] Skipping {item_name} (HSN {hsn}), qty {quantity_to_increment}")
        return False
    try:
        safe_hsn      = str(hsn or "").strip()
        stripped_name = item_name.strip()

        query = {
            "itemName": {
                "$regex":   f"^\\s*{re.escape(stripped_name)}\\s*$",
                "$options": "i",
            },
            "is_active": True,
        }
        if safe_hsn:
            query["hsn"] = safe_hsn

        # ── Step 1: If approved_quantity is null, set it to 0 first ──────
        items_collection.update_one(
            {**query, "approved_quantity": None},
            {"$set": {"approved_quantity": 0}},
        )

        # ── Step 2: Now safely increment ─────────────────────────────────
        result = items_collection.find_one_and_update(
            query,
            {
                "$inc": {"approved_quantity": quantity_to_increment},
                "$set": {
                    "lastmodified_date": datetime.utcnow(),
                    "lastmodified_by":   auth_user_id,
                },
            },
            return_document=True,
        )
        if not result:
            logger.warning(f"[reduce_stock] No item found for {item_name} (HSN {hsn}).")
            return False
        logger.debug(
            f"[reduce_stock] {item_name} (HSN {hsn}): "
            f"approved_quantity +{quantity_to_increment}"
        )
        return True
    except Exception as e:
        logger.error(f"[reduce_stock] Error updating {item_name} (HSN {hsn}): {e}")
        return False

def add_back_stock(item_id, hsn, quantity_to_subtract, employee_id=None):
    try:
        if item_id is None or int(quantity_to_subtract) <= 0:
            return False

        safe_hsn = str(hsn or "").strip()
        try:
            query = {"item_id": int(item_id), "is_active": True}
        except (ValueError, TypeError):
            query = {"item_id": item_id, "is_active": True}

        if safe_hsn:
            query["hsn"] = safe_hsn

        # ── Initialize approved_quantity to 0 if null ─────────────────────
        items_collection.update_one(
            {**query, "approved_quantity": None},
            {"$set": {"approved_quantity": 0}},
        )

        item_doc = items_collection.find_one(query)
        if not item_doc:
            logger.warning(
                f"[add_back_stock] No item found for item_id={item_id} (HSN {hsn})."
            )
            return False

        current_approved = int(item_doc.get("approved_quantity", 0) or 0)
        new_approved     = max(0, current_approved - int(quantity_to_subtract))

        items_collection.update_one(
            {"_id": item_doc["_id"]},
            {
                "$set": {
                    "approved_quantity": new_approved,
                    "lastmodified_by":   employee_id,
                    "lastmodified_date": datetime.utcnow(),
                }
            },
        )
        logger.debug(
            f"[add_back_stock] item_id={item_id} (HSN {hsn}): "
            f"approved_quantity {current_approved} → {new_approved}"
        )
        return True

    except Exception as e:
        logger.error(f"[add_back_stock] Error for item_id={item_id}: {e}")
        return False

@api_view(["PATCH"])
@permission_classes([HasRolePermission])
def add_back_traveller_stock(request):
    """Restore stock by subtracting from approved_quantity using item_id."""
    item_id     = request.data.get("item_id")
    hsn         = request.data.get("hsn", "")
    quantity    = request.data.get("quantity", 0)
    employee_id = request.data.get("auth-user-id", "Unknown User")

    if not item_id or not quantity:
        return Response(
            {"success": False, "error": "item_id and quantity are required"},
            status=400,
        )

    try:
        qty = int(quantity)
        if qty <= 0:
            return Response(
                {"success": False, "error": "quantity must be greater than 0"},
                status=400,
            )

        success = add_back_stock(
            item_id=item_id,
            hsn=hsn,
            quantity_to_subtract=qty,
            employee_id=employee_id,
        )

        if not success:
            return Response(
                {
                    "success": False,
                    "error":   f"Item not found for item_id={item_id}",
                },
                status=404,
            )

        return Response({
            "success":      True,
            "item_id":      item_id,
            "restored_qty": qty,
        })

    except Exception as e:
        logger.error(f"Error in add_back_traveller_stock: {e}")
        return Response({"success": False, "error": str(e)}, status=500)


# 🔥 Utility to clean ObjectId
def clean_object_ids(data):
    if isinstance(data, dict):
        return {k: clean_object_ids(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_object_ids(i) for i in data]
    elif isinstance(data, ObjectId):
        return str(data)
    return data


@api_view(['POST'])
@permission_classes([HasRolePermission])
def create_travellers_in(request):
    try:
        data = request.data

        mapped_data = {
            'purchase_category': data.get('purchaseCategory'),
            'vendor_id': data.get('vendor_id'),
            'date': data.get('date'),
            'invoice_no': data.get('invoiceNo'),
            'invoice_date': data.get('invoiceDate'),
            'credit_period': data.get('creditPeriod'),
            'due_date': data.get('dueDate'),
            'payment_mode': data.get('paymentMode'),
        }

        # 🔥 Clean items (important)
        items = data.get('items', [])
        mapped_data['items'] = clean_object_ids(items)

        # Summary mapping
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
            value = summary.get(frontend_field, 0)
            mapped_data[backend_field] = float(value) if value not in ["", None] else 0

        # Audit
        employee_id = data.get('auth-user-id')
        mapped_data['created_by'] = employee_id if employee_id else 'Anonymous'
        mapped_data['is_active'] = True

        # Payment status
        net_invoice_amount = float(mapped_data.get('net_invoice_amount', 0))
        mapped_data['payment_status'] = [{
            'status': 'Not Paid',
            'amount_paid': 0.0,
            'pending_amount': net_invoice_amount,
            'payment_method': None,
            'payment_details': None,
            'paid_by': None,
        }]
        mapped_data['overall_payment_status'] = 'Not Paid'

        serializer = TravellersINSerializer(data=mapped_data)

        if serializer.is_valid():
            travellers_in = serializer.save()

            # 🔥 IMPORTANT: use serializer.data (not re-serialize)
            return JsonResponse({
                'status': 'success',
                'message': 'TravellersIN record created successfully',
                'grn_number': travellers_in.grn_number,
                'data': serializer.data
            }, status=201)

        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Validation failed',
                'errors': serializer.errors,
            }, status=400)

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_travellers_in_list(request):
    """List TravellersIN records with pagination, date filtering, and vendor details."""
    try:
        from_date_str = request.GET.get('from_date')
        to_date_str   = request.GET.get('to_date')
        from_date     = None
        to_date       = None

        if from_date_str:
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'status': 'error', 'message': 'Invalid from_date. Expected YYYY-MM-DD'},
                    status=400,
                )

        if to_date_str:
            try:
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'status': 'error', 'message': 'Invalid to_date. Expected YYYY-MM-DD'},
                    status=400,
                )

        all_records = list(TravellersIN.objects.all().order_by('-created_date'))

        if from_date or to_date:
            filtered = []
            for r in all_records:
                inv_date = getattr(r, 'invoice_date', None)
                if inv_date is None:
                    continue
                if hasattr(inv_date, 'date'):
                    inv_date = inv_date.date()
                if from_date and inv_date < from_date:
                    continue
                if to_date and inv_date > to_date:
                    continue
                filtered.append(r)
            all_records = filtered

        try:
            page      = max(1, int(request.GET.get('page', 1)))
            page_size = max(1, int(request.GET.get('page_size', 10)))
        except ValueError:
            page, page_size = 1, 10

        total_records = len(all_records)
        total_pages   = (total_records + page_size - 1) // page_size
        start_index   = (page - 1) * page_size
        page_records  = all_records[start_index:start_index + page_size]

        response_data = []

        for obj in page_records:
            try:
                vendor_details = {
                    'vendor': '', 'contact_person': '',
                    'phone': '', 'address': '', 'email': '',
                }
                if obj.vendor_id:
                    try:
                        vendor = Vendors.objects.get(vendor_id=obj.vendor_id)
                        vendor_details = {
                            'vendor':         vendor.name,
                            'contact_person': vendor.contactPerson or '',
                            'phone':          vendor.phone or '',
                            'address':        f"{vendor.addressLine1}, {vendor.addressLine2}, "
                                              f"{vendor.city}, {vendor.state or ''}".strip(', '),
                            'email':          vendor.email or '',
                        }
                    except Vendors.DoesNotExist:
                        logger.warning(f"Vendor {obj.vendor_id} not found")

                # ── Items — resolve itemName from Items model via item_id ──
                items = getattr(obj, 'items', [])
                if isinstance(items, str):
                    try:
                        items = json.loads(items)
                        if not isinstance(items, list):
                            items = []
                    except json.JSONDecodeError:
                        items = []
                elif not isinstance(items, list):
                    items = []

                for item in items:
                    item_id = item.get('item_id')
                    if item_id is not None:
                        resolved_name = get_item_name_by_id(item_id)
                        if resolved_name:
                            item['itemName'] = resolved_name

                    for field in [
                        'itemValue', 'packingPrice', 'unitPrice', 'cgstAmt',
                        'sgstAmt', 'purchaseCost', 'mrp', 'tax',
                        'cgstPercent', 'sgstPercent',
                    ]:
                        if field in item:
                            item[field] = convert_decimal128_to_float(item[field])

                raw_ps = getattr(obj, 'payment_status', [])
                if isinstance(raw_ps, str):
                    try:
                        payment_status = json.loads(raw_ps)
                        if not isinstance(payment_status, list):
                            payment_status = []
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Invalid JSON in payment_status for GRN {obj.grn_number}"
                        )
                        payment_status = []
                elif isinstance(raw_ps, list):
                    payment_status = raw_ps
                else:
                    payment_status = []

                for entry in payment_status:
                    for field in ['amount_paid', 'pending_amount']:
                        if field in entry:
                            entry[field] = convert_decimal128_to_float(entry[field])

                total_amount = convert_decimal128_to_float(getattr(obj, 'total_amount', 0))
                total_amount_paid = round(
                    sum(
                        convert_decimal128_to_float(e.get('amount_paid', 0))
                        for e in payment_status
                    ),
                    2,
                )

                if payment_status:
                    latest          = payment_status[-1]
                    pending_amount  = convert_decimal128_to_float(latest.get('pending_amount', 0))
                    overall_status  = latest.get('status', 'Not Paid')
                    payment_details = latest
                else:
                    pending_amount  = max(0.0, total_amount - total_amount_paid)
                    overall_status  = 'Not Paid'
                    payment_details = {
                        'status':          'Not Paid',
                        'amount_paid':     0.0,
                        'pending_amount':  total_amount,
                        'payment_method':  None,
                        'payment_details': None,
                        'paid_by':         None,
                    }

                item_data = {
                    'id':                str(getattr(obj, '_id', None)),
                    'grn_id':            getattr(obj, 'grn_id', None),
                    'grn_number':        getattr(obj, 'grn_number', None),
                    'vendor_id':         getattr(obj, 'vendor_id', None),
                    **vendor_details,
                    'payment_status':    payment_status,
                    'payment_details':   payment_details,
                    'overall_status':    overall_status,
                    'total_amount_paid': total_amount_paid,
                    'pending_amount':    pending_amount,
                    'purchase_category': getattr(obj, 'purchase_category', None),
                    'invoice_no':        getattr(obj, 'invoice_no', None),
                    'credit_period':     getattr(obj, 'credit_period', None) or '',
                    'payment_mode':      getattr(obj, 'payment_mode', None),
                    'remarks':           getattr(obj, 'remarks', None) or '',
                    'created_by':        getattr(obj, 'created_by', None),
                    'items':             items,
                    'lastmodified_by':   getattr(obj, 'lastmodified_by', None),
                }

                for field in [
                    'date', 'invoice_date', 'due_date',
                    'created_date', 'lastmodified_date',
                ]:
                    value = getattr(obj, field, None)
                    item_data[field] = (
                        value.isoformat() if hasattr(value, 'isoformat')
                        else str(value) if value else None
                    )

                for field in [
                    'non_taxable_amount', 'taxable_amount', 'tax_paid_to_supplier',
                    'local_tax', 'cgst', 'sgst', 'igst', 'cess', 'central_sales_tax',
                    'round_amount', 'total_amount', 'tax_on_free_items', 'total_discount',
                    'net_invoice_amount', 'quotation_rate', 'courier_transport_charge',
                ]:
                    item_data[field] = convert_decimal128_to_float(
                        getattr(obj, field, None)
                    )

                response_data.append(item_data)

            except Exception as item_error:
                logger.error(
                    f"Error processing GRN {obj.grn_number}: "
                    f"{item_error}\n{traceback.format_exc()}"
                )
                response_data.append({
                    'id':             str(getattr(obj, '_id', None)),
                    'grn_number':     getattr(obj, 'grn_number', None),
                    'vendor_id':      getattr(obj, 'vendor_id', None),
                    'vendor': '', 'contact_person': '', 'phone': '', 'address': '',
                    'error':          f'Processing failed: {item_error}',
                })

        return Response({
            'status': 'success',
            'data':   response_data,
            'pagination': {
                'current_page':  page,
                'total_pages':   total_pages,
                'total_records': total_records,
                'has_next':      page < total_pages,
                'has_previous':  page > 1,
            },
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in get_travellers_in_list: {e}\n{traceback.format_exc()}")
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def update_payment_status(request):
    """Record a single full payment for a GRN — replaces any existing payment_status."""
    grn_number = request.query_params.get('grn_number')
    grn_id     = request.query_params.get('grn_id')
    employee_id = request.data.get('auth-user-id')

    if not grn_number or not grn_id:
        return Response(
            {'status': 'error', 'message': 'Missing grn_number or grn_id in query parameters'},
            status=400,
        )

    grn_number = urllib.parse.unquote(grn_number).strip()

    try:
        data = request.data
        if not isinstance(data, dict):
            return Response(
                {'status': 'error', 'message': 'Request body must be a JSON object'},
                status=400,
            )

        for field in ['payment_method', 'payment_date', 'status']:
            if not data.get(field):
                return Response(
                    {'status': 'error', 'message': f'Missing required field: {field}'},
                    status=400,
                )

        if data['status'] != 'Paid':
            return Response(
                {'status': 'error', 'message': 'Status must be "Paid"'},
                status=400,
            )

        try:
            payment_date = data['payment_date']
            datetime.strptime(payment_date, '%d/%m/%Y')
        except (ValueError, TypeError):
            return Response(
                {'status': 'error', 'message': 'Invalid payment_date format. Expected DD/MM/YYYY'},
                status=400,
            )

        current_doc = purchases_collection.find_one({
            "grn_number": grn_number,
            "grn_id": int(grn_id)
        })
        if not current_doc:
            return Response(
                {'status': 'error', 'message': f'No record found for GRN {grn_number}'},
                status=404,
            )

        # ── Block re-payment if already paid ──────────────────────────────
        if current_doc.get('overall_payment_status') == 'Paid':
            return Response(
                {'status': 'error', 'message': f'GRN {grn_number} is already fully paid'},
                status=400,
            )

        # ── Use net_invoice_amount (after round-off) as the amount paid ───
        amount_paid = round(
            convert_decimal128_to_float(
                current_doc.get('net_invoice_amount') or current_doc.get('total_amount', 0)
            ),
            2,
        )

        # ── Build a single payment entry (replaces entire payment_status) ─
        payment_entry = {
            'status':          'Paid',
            'amount_paid':     amount_paid,
            'pending_amount':  0.0,
            'payment_method':  data['payment_method'],
            'payment_details': (
                None if data['payment_method'] == 'Cash'
                else data.get('payment_details')
            ),
            'payment_date':    payment_date,
            'paid_by':         employee_id,
            'timestamp':       timezone.now().isoformat(),
        }

        result = purchases_collection.update_one(
            {
                "grn_number": grn_number,
                "grn_id": int(grn_id)
            },
            {
                "$set": {
                    # Overwrite entirely — single payment, no history list
                    "payment_status":         json.dumps([payment_entry]),
                    "overall_payment_status": "Paid",
                    "total_amount_paid":      amount_paid,
                    "pending_amount":         0.0,
                    "lastmodified_date":      timezone.now(),
                    "lastmodified_by":        employee_id or 'Anonymous',
                }
            },
        )

        if result.matched_count >= 1:
            return Response({
                'status':  'success',
                'message': f'Payment recorded for GRN {grn_number}',
                'data': {
                    'amount_paid':    amount_paid,
                    'pending_amount': 0.0,
                    'payment_method': payment_entry['payment_method'],
                    'payment_date':   payment_entry['payment_date'],
                    'paid_by':        employee_id,
                    'timestamp':      payment_entry['timestamp'],
                },
            })

        return Response(
            {'status': 'error', 'message': f'Failed to update record for GRN {grn_number}'},
            status=500,
        )

    except Exception as e:
        return Response({
            'status':  'error',
            'message': f'Failed to update payment status: {e}',
            'trace':   traceback.format_exc(),
        }, status=500)


@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def travellers_in_update(request, grn_number, grn_id):
    """Update an existing TravellersIN record by GRN number."""
    try:
        document = purchases_collection.find_one({"grn_number": grn_number,"grn_id": int(grn_id)})
        if not document:
            return Response(
                {'status': 'error', 'message': f'No record found for GRN {grn_number}'},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = request.data

        # ── Resolve itemName for each item using item_id from Items model ─
        raw_items      = data.get('items', [])
        resolved_items = []
        for item in raw_items:
            item_copy = dict(item)
            item_id   = item_copy.get('item_id')
            if item_id is not None:
                resolved_name = get_item_name_by_id(item_id)
                if resolved_name:
                    item_copy['itemName'] = resolved_name
                else:
                    logger.warning(
                        f"[travellers_in_update] Could not resolve itemName "
                        f"for item_id={item_id}, leaving field as-is"
                    )
            resolved_items.append(item_copy)

        # ── Map frontend field names → backend field names ────────────────
        mapped_data = {
            'purchase_category': data.get('purchaseCategory'),
            'vendor_id':         data.get('vendor_id'),
            'invoice_no':        data.get('invoiceNo'),
            'credit_period':     data.get('creditPeriod', ''),
            'payment_mode':      data.get('paymentMode'),
            'items':             json.dumps(resolved_items),
            'date':              data.get('date'),
            'invoice_date':      data.get('invoiceDate'),
            'due_date':          data.get('dueDate'),
            'lastmodified_by':   data.get('auth-user-id') or 'Anonymous',
            'lastmodified_date': datetime.utcnow().isoformat(),
        }

        # ── Summary / numeric fields ──────────────────────────────────────
        summary = data.get('summary', {})
        summary_mapping = {
            'non_taxable_amount':       'nonTaxableAmount',
            'taxable_amount':           'taxableAmount',
            'tax_paid_to_supplier':     'taxPaidToSupplier',
            'local_tax':                'localTax',
            'remarks':                  'remarks',
            'cgst':                     'cgst',
            'sgst':                     'sgst',
            'igst':                     'igst',
            'cess':                     'cess',
            'central_sales_tax':        'centralSalesTax',
            'round_amount':             'roundAmount',
            'total_amount':             'totalAmount',
            'tax_on_free_items':        'taxOnFreeItems',
            'total_discount':           'totalDiscount',
            'net_invoice_amount':       'netInvoiceAmount',
            'quotation_rate':           'quotationRate',
            'courier_transport_charge': 'courierTransportCharge',
        }
        for backend_field, frontend_field in summary_mapping.items():
            mapped_data[backend_field] = convert_decimal128_to_float(
                summary.get(frontend_field, document.get(backend_field, 0))
            )

        # ── Validate ──────────────────────────────────────────────────────
        serializer = TravellersINSerializer(data=mapped_data, partial=True)
        if not serializer.is_valid():
            return Response(
                {
                    'status':  'error',
                    'message': 'Validation failed',
                    'errors':  serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        update_data = dict(serializer.validated_data)

        # Convert date → datetime so MongoDB stores as ISODate
        for field in ('date', 'invoice_date', 'due_date'):
            val = update_data.get(field)
            if val is not None and isinstance(val, date) and not isinstance(val, datetime):
                update_data[field] = datetime(val.year, val.month, val.day)

        update_data['lastmodified_date'] = datetime.utcnow()
        update_data['lastmodified_by']   = data.get('auth-user-id') or 'Anonymous'

        # Convert numeric summary fields → Decimal128 for MongoDB
        numeric_fields = [
            'non_taxable_amount', 'taxable_amount', 'tax_paid_to_supplier',
            'local_tax', 'cgst', 'sgst', 'igst', 'cess', 'central_sales_tax',
            'round_amount', 'total_amount', 'tax_on_free_items', 'total_discount',
            'net_invoice_amount', 'quotation_rate', 'courier_transport_charge',
        ]
        for field in numeric_fields:
            if field in update_data:
                update_data[field] = Decimal128(str(update_data[field]))

        # ── Recalculate payment_status with new net_invoice_amount ────────
        new_net_invoice_amount = convert_decimal128_to_float(
            summary.get('netInvoiceAmount', document.get('net_invoice_amount', 0))
        )

        raw_ps = document.get('payment_status', [])
        if isinstance(raw_ps, str):
            try:
                current_payment_status = json.loads(raw_ps)
                if not isinstance(current_payment_status, list):
                    current_payment_status = []
            except json.JSONDecodeError:
                current_payment_status = []
        elif isinstance(raw_ps, list):
            current_payment_status = raw_ps
        else:
            current_payment_status = []

        updated_payment_status = []
        for entry in current_payment_status:
            if entry.get('status') == 'Not Paid':
                updated_payment_status.append({
                    **entry,
                    'pending_amount': new_net_invoice_amount,
                    'amount_paid':    0.0,
                })
            else:
                updated_payment_status.append(entry)

        if not updated_payment_status:
            updated_payment_status = [{
                'status':          'Not Paid',
                'amount_paid':     0.0,
                'pending_amount':  new_net_invoice_amount,
                'payment_method':  None,
                'payment_details': None,
                'paid_by':         None,
            }]

        update_data['payment_status'] = json.dumps(updated_payment_status)
        update_data['overall_payment_status'] = (
            'Paid'
            if all(e.get('status') == 'Paid' for e in updated_payment_status)
            else 'Not Paid'
        )

        # ── Persist — match only by grn_number ───────────────────────────
        result = purchases_collection.update_one(
    {
        "grn_number": grn_number,
        "grn_id": int(grn_id)
    },
    {"$set": update_data},
    upsert=False,
)
        if result.matched_count >= 1:
            updated_doc = purchases_collection.find_one({
    "grn_number": grn_number,
    "grn_id": int(grn_id)
})
            return Response({
                'status':  'success',
                'message': f'TravellersIN record {grn_number} updated successfully',
                'data':    clean_mongo_document(updated_doc),
            }, status=status.HTTP_200_OK)

        return Response(
            {'status': 'error', 'message': f'No record found for GRN {grn_number}'},
            status=status.HTTP_404_NOT_FOUND,
        )

    except Exception as e:
        logger.error(
            f"Error in travellers_in_update for GRN {grn_number}: "
            f"{e}\n{traceback.format_exc()}"
        )
        return Response(
            {'status': 'error', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_previous_purchases(request):
    """Return past purchase records matching a given HSN and item_id."""
    hsn     = request.GET.get('hsn')
    item_id = request.GET.get('item_id')

    if not hsn or not item_id:
        return Response(
            {'status': 'error', 'message': 'HSN and item_id are required'},
            status=400,
        )

    try:
        documents = purchases_collection.find({})
        matched_purchases = []

        for doc in documents:
            items = doc.get('items', [])
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except json.JSONDecodeError:
                    continue
            elif not isinstance(items, list):
                continue

            payment_details = doc.get('payment_details', {})
            if isinstance(payment_details, str):
                try:
                    payment_details = json.loads(payment_details)
                except json.JSONDecodeError:
                    payment_details = {}
            if not isinstance(payment_details, dict):
                payment_details = {}
            for field in ['amount_paid', 'pending_amount']:
                if field in payment_details:
                    payment_details[field] = convert_decimal128_to_float(
                        payment_details[field]
                    )

            for item in items:
                doc_item_id = str(item.get('item_id', '')).strip()
                doc_hsn     = str(item.get('hsn', '')).strip()

                if doc_item_id == str(item_id).strip() and doc_hsn == hsn.strip():
                    resolved_name    = get_item_name_by_id(item.get('item_id'))
                    item['itemName'] = resolved_name or item.get('itemName', '')

                    doc['matched_item']    = item
                    doc['payment_details'] = payment_details

                    vendor_name = None
                    vendor_id   = doc.get('vendor_id')
                    if vendor_id:
                        try:
                            vendor_doc = vendors_collection.find_one({
                                "$or": [
                                    {"vendor_id": str(vendor_id).strip()},
                                    {"vendor_id": int(vendor_id)},
                                ]
                            })
                            if vendor_doc:
                                vendor_name = vendor_doc.get('name')
                        except Exception:
                            pass
                    doc['vendor_name'] = vendor_name

                    matched_purchases.append(clean_mongo_document(doc))
                    break

        return Response({'status': 'success', 'data': matched_purchases}, status=200)

    except Exception as e:
        logger.error(f"Error in get_previous_purchases: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([HasRolePermission])
def travellers_stock(request):
    item_id    = request.GET.get("item_id")
    hsn_number = request.GET.get("hsn")
    try:
        query = {"is_active": True}

        if item_id is not None:
            try:
                query["item_id"] = int(item_id)
            except (ValueError, TypeError):
                query["item_id"] = item_id

        if hsn_number:
            query["hsn"] = hsn_number.strip()

        item_doc = items_collection.find_one(query)
        if not item_doc:
            return JsonResponse({"success": False, "error": "Item not found"}, status=404)

        total_quantity    = int(item_doc.get("total_quantity", 0) or 0)
        # ── Guard against null approved_quantity ──────────────────────────
        approved_quantity = int(item_doc.get("approved_quantity") or 0)
        available_stock   = total_quantity - approved_quantity

        return JsonResponse({
            "success":           True,
            "item_id":           item_doc.get("item_id"),
            "itemName":          item_doc.get("itemName"),
            "hsn":               item_doc.get("hsn"),
            "total_quantity":    total_quantity,
            "approved_quantity": approved_quantity,
            "total_stock":       available_stock,
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
    
@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([HasRolePermission])
def travellers_intent(request):

    # ── GET ───────────────────────────────────────────────────────────────────
    if request.method == 'GET':
        intents = TravellerIntent.objects.all()

        # ── Date filtering ────────────────────────────────────────────────────
        from_date_str = request.query_params.get('from_date')
        to_date_str   = request.query_params.get('to_date')

        if from_date_str:
            try:
                from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
                intents = intents.filter(date__gte=from_date)
            except ValueError:
                return Response(
                    {'error': 'Invalid from_date format. Expected YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if to_date_str:
            try:
                to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
                intents = intents.filter(date__lte=to_date)
            except ValueError:
                return Response(
                    {'error': 'Invalid to_date format. Expected YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        # ─────────────────────────────────────────────────────────────────────

        serializer = TravellerIntentSerializer(intents, many=True)
        data       = serializer.data

        # Resolve itemName for each item in each intent using item_id
        for intent in data:
            raw_items = intent.get('items', [])
            if isinstance(raw_items, str):
                try:
                    raw_items = json.loads(raw_items)
                except json.JSONDecodeError:
                    raw_items = []

            resolved_items = []
            for item in raw_items:
                item_copy = dict(item)
                item_id   = item_copy.get('item_id')
                if item_id is not None:
                    resolved_name = get_item_name_by_id(item_id)
                    if resolved_name:
                        item_copy['itemName'] = resolved_name
                resolved_items.append(item_copy)

            intent['items'] = resolved_items

        return Response(data)

    # ── POST ──────────────────────────────────────────────────────────────────
    elif request.method == 'POST':
        intent_date_str = request.data.get('date')
        if intent_date_str:
            try:
                intent_date = datetime.strptime(intent_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Expected YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            intent_date = date.today()

        financial_year_start = (
            intent_date.year if intent_date.month >= 4 else intent_date.year - 1
        )
        year_suffix = str(financial_year_start)[-2:]
        prefix      = f"IN0{year_suffix}/"

        last_intent = (
            TravellerIntent.objects.filter(intent_number__startswith=prefix)
            .order_by('-intent_number')
            .first()
        )
        last_number = (
            int(last_intent.intent_number.split('/')[-1])
            if last_intent and last_intent.intent_number
            else 0
        )
        new_intent_number = f"{prefix}{last_number + 1:05d}"

        # ── Resolve itemName for each item from Items model via item_id ───
        raw_items      = request.data.get('items', [])
        resolved_items = []
        for item in raw_items:
            item_copy = dict(item)
            item_id   = item_copy.get('item_id')
            if item_id is not None:
                resolved_name = get_item_name_by_id(item_id)
                if resolved_name:
                    item_copy['itemName'] = resolved_name
                else:
                    logger.warning(
                        f"[travellers_intent POST] Could not resolve itemName "
                        f"for item_id={item_id}"
                    )
            resolved_items.append(item_copy)

        data                  = request.data.copy()
        data['intent_number'] = new_intent_number
        data['created_by']    = request.data.get("auth-user-id")
        data['items']         = resolved_items

        serializer = TravellerIntentSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        logger.warning("Serializer errors: %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # ── PATCH ─────────────────────────────────────────────────────────────────
    elif request.method == 'PATCH':
        intent_id = request.data.get("intent_id")
        item_id   = request.data.get("item_id")

        if not intent_id or not item_id:
            return Response({"error": "intent_id and item_id required"}, status=400)

        try:
            intent = TravellerIntent.objects.get(id=intent_id)
        except TravellerIntent.DoesNotExist:
            return Response({"error": "Intent not found"}, status=404)

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
                delta        = new_approved - old_approved
                if delta > 0:
                    resolved_name       = get_item_name_by_id(item.get("item_id"))
                    item_name_for_stock = resolved_name or item.get("itemName", "")
                    if not reduce_stock(
                        item_name_for_stock,
                        item.get("hsn"),
                        delta,
                        request.data.get("auth-user-id"),
                    ):
                        return Response({"error": "Insufficient stock"}, status=400)
                # Always keep itemName resolved from model
                resolved_name = get_item_name_by_id(item.get("item_id"))
                if resolved_name:
                    item["itemName"] = resolved_name
                item["approved"] = new_approved
                item["status"]   = request.data.get("status", item.get("status"))
            updated_items.append(item)

        intent.items = json.dumps(updated_items)
        intent.save()
        return Response({"success": True, "message": "Intent updated"})


@api_view(["PATCH"])
@permission_classes([HasRolePermission])
def update_intent_item(request):
    intent_number = request.data.get("intent_number")
    date_str      = request.data.get("date")
    items_updates = request.data.get("items", [])
    employee_id   = request.data.get("auth-user-id")

    if not all([intent_number, date_str, items_updates]):
        return Response(
            {"error": "intent_number, date, and items are required."},
            status=400,
        )

    try:
        intent = TravellerIntent.objects.get(
            intent_number=intent_number, date=parse_date(date_str)
        )
    except TravellerIntent.DoesNotExist:
        return Response({"error": "Intent not found"}, status=404)

    # ── Always unwrap to a plain list, no matter how many times it was stringified ──
    items = intent.items
    while isinstance(items, str):
        try:
            items = json.loads(items)
        except (json.JSONDecodeError, ValueError):
            break
    if not isinstance(items, list):
        items = []
    # ─────────────────────────────────────────────────────────────────────────────

    total_stock_reduced = 0
    restored_quantities = []

    # ── Normalise status values coming from frontend ──────────────────────────
    STATUS_MAP = {
        "Approve":           "Approved",
        "Partially Approve": "Partially Approved",
        "Reject":            "Rejected",
    }

    for update in items_updates:
        item_id      = update.get("item_id")
        raw_status   = update.get("status")
        new_status   = STATUS_MAP.get(raw_status, raw_status)   # ← normalise here
        new_quantity = update.get("quantity")
        approved_qty = update.get("approved_qty", None)

        for item in items:
            if item.get("item_id") != item_id:
                continue

            previous_approved = int(item.get("approved") or 0)

            resolved_name = get_item_name_by_id(item.get("item_id"))
            if resolved_name:
                item["itemName"] = resolved_name

            if new_quantity is not None:
                item["quantity"] = int(new_quantity)
            if new_status is not None:
                item["status"] = new_status      # stored as "Approved" / "Rejected" etc.

            stock_to_reduce = 0

            if new_status in ["Approved", "Partially Approved"]:
                new_approved        = (
                    int(approved_qty) if approved_qty is not None
                    else int(item.get("quantity") or 0)
                )
                item["approved"]    = new_approved
                item["approved_by"] = employee_id
                stock_to_reduce     = new_approved - previous_approved

            elif new_status in ["Rejected", "Pending"]:
                item["approved"]    = 0
                item["approved_by"] = (
                    "Pending" if new_status == "Pending" else employee_id
                )
                stock_to_reduce = 0 - previous_approved
                restore_amount  = abs(stock_to_reduce)
                if restore_amount > 0:
                    restored_quantities.append({
                        'item_id':  item.get("item_id"),
                        'hsn':      str(item.get("hsn", "")),
                        'quantity': restore_amount,
                    })

            if stock_to_reduce > 0:
                if not reduce_stock(
                    item.get("itemName"),
                    str(item.get("hsn", "")),
                    stock_to_reduce,
                    employee_id,
                ):
                    return Response(
                        {"error": f"Insufficient stock to approve item_id={item.get('item_id')}."},
                        status=400,
                    )
                total_stock_reduced += stock_to_reduce

            elif stock_to_reduce < 0:
                restore_amount = abs(stock_to_reduce)
                if not add_back_stock(
                    item.get("item_id"),
                    str(item.get("hsn", "")),
                    restore_amount,
                    employee_id,
                ):
                    return Response(
                        {"error": f"Failed to restore stock for item_id={item.get('item_id')}."},
                        status=400,
                    )

            break

    total_approved_qty = sum(
        int(i.get("approved", 0) or 0) for i in items
        if i.get("status") in ["Approved", "Partially Approved"]
    )

    # ── Single json.dumps — never double-stringify ────────────────────────────
    intent.items             = items 
    intent.approved_qty      = total_approved_qty
    intent.lastmodified_by   = str(employee_id)
    intent.lastmodified_date = timezone.now()
    intent.save()

    return Response({
        "success":             True,
        "total_stock_reduced": total_stock_reduced,
        "approved_qty":        total_approved_qty,
        "items":               items,
        "restored_quantities": restored_quantities,
    }, status=200)


@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def soft_delete_intent_item(request):
    """Mark a single item within a TravellerIntent as inactive."""
    intent_number = request.query_params.get('intent_number')
    date_str      = request.query_params.get('date')
    item_id       = request.query_params.get('item_id')

    if not (intent_number and date_str and item_id):
        return Response(
            {'error': 'intent_number, date, and item_id are required.'},
            status=400,
        )

    try:
        intent = TravellerIntent.objects.get(
            intent_number=intent_number, date=parse_date(date_str)
        )
    except TravellerIntent.DoesNotExist:
        return Response({'error': 'Intent not found'}, status=404)

    items   = json.loads(intent.items) if isinstance(intent.items, str) else intent.items
    updated = False
    for item in items:
        if str(item.get('item_id')) == str(item_id):
            item['is_active'] = False
            updated = True
            break

    if not updated:
        return Response({'error': 'Item not found'}, status=404)

    intent.items             = json.dumps(items)
    intent.lastmodified_by   = request.query_params.get('auth-user-id', 'unknown user')
    intent.lastmodified_date = timezone.now()
    intent.save()
    return Response({'message': 'Item soft-deleted successfully'}, status=200)


@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def soft_delete_intent(request):
    """Mark all matching TravellerIntent records as inactive."""
    intent_number = request.query_params.get('intent_number')
    date_str      = request.query_params.get('date')

    if not intent_number or not date_str:
        return Response({"success": False, "error": "Missing parameters"}, status=400)

    filter_date = parse_date(date_str)
    if not filter_date:
        return Response(
            {"success": False, "error": "Invalid date format. Expected YYYY-MM-DD"},
            status=400,
        )

    intents = TravellerIntent.objects.filter(
        intent_number=intent_number, date=filter_date
    )
    if not intents.exists():
        return Response({"success": False, "error": "Intent not found"}, status=404)

    count = intents.count()
    intents.update(
        is_active=False,
        lastmodified_by=request.query_params.get('auth-user-id', 'unknown user'),
        lastmodified_date=timezone.now(),
    )
    return Response({
        "success": True,
        "message": f"{count} intent(s) soft-deleted successfully",
    })


@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_travellers_intent_by_date_range(request):
    """Filter TravellerIntent records by date range."""
    from_date_str = request.query_params.get('from_date')
    to_date_str   = request.query_params.get('to_date')

    queryset = TravellerIntent.objects.all()

    if from_date_str:
        from_date = parse_date(from_date_str)
        if not from_date:
            return Response(
                {'error': 'Invalid from_date format. Expected YYYY-MM-DD'},
                status=400,
            )
        queryset = queryset.filter(date__gte=from_date)

    if to_date_str:
        to_date = parse_date(to_date_str)
        if not to_date:
            return Response(
                {'error': 'Invalid to_date format. Expected YYYY-MM-DD'},
                status=400,
            )
        queryset = queryset.filter(date__lte=to_date)

    # Resolve itemName for each item in each intent using item_id
    serializer = TravellerIntentSerializer(queryset, many=True)
    data       = serializer.data

    for intent in data:
        raw_items = intent.get('items', [])
        if isinstance(raw_items, str):
            try:
                raw_items = json.loads(raw_items)
            except json.JSONDecodeError:
                raw_items = []

        resolved_items = []
        for item in raw_items:
            item_copy = dict(item)
            item_id   = item_copy.get('item_id')
            if item_id is not None:
                resolved_name = get_item_name_by_id(item_id)
                if resolved_name:
                    item_copy['itemName'] = resolved_name
            resolved_items.append(item_copy)

        intent['items'] = resolved_items

    return Response(data, status=200)