# import os
# import json
# import certifi
# import traceback
# from datetime import date, datetime
# from decimal import Decimal
# from bson.decimal128 import Decimal128
# from bson.objectid import ObjectId
# from pymongo import MongoClient
# from django.utils import timezone
# from django.views.decorators.csrf import csrf_exempt
# from rest_framework.decorators import api_view
# from rest_framework.response import Response
# from rest_framework import status
# import logging
# from dotenv import load_dotenv

# logger = logging.getLogger(__name__)
# load_dotenv()

# # ------------------- MongoDB Setup -------------------
# env_type = os.environ.get("ENV_CLASSIFICATION", "local")
# mongo_uri = os.environ.get("GLOBAL_DB_HOST")
# db_name = os.environ.get("STORETRUST_DB_NAME", "StoreTrust")

# if env_type in ["test", "prod"]:
#     client = MongoClient(mongo_uri)
# else:
#     client = MongoClient(mongo_uri, tls=True, tlsCAFile=certifi.where())

# db = client[db_name]
# collection = db["college_in"]

# # ------------------- Helpers -------------------

# def convert_decimal128_to_float(value):
#     """Convert Decimal128 or numeric types to float safely"""
#     if value is None:
#         return 0.0
#     if isinstance(value, Decimal128):
#         return float(value.to_decimal())
#     elif isinstance(value, Decimal):
#         return float(value)
#     elif isinstance(value, (int, float)):
#         return float(value)
#     elif isinstance(value, str):
#         try:
#             return float(value)
#         except ValueError:
#             return 0.0
#     return 0.0

# def clean_mongo_document(doc):
#     """Convert Decimal128 and ObjectId to JSON-safe types recursively"""
#     if isinstance(doc, dict):
#         return {k: clean_mongo_document(v) for k, v in doc.items()}
#     elif isinstance(doc, list):
#         return [clean_mongo_document(i) for i in doc]
#     elif isinstance(doc, Decimal128):
#         return float(doc.to_decimal())
#     elif isinstance(doc, ObjectId):
#         return str(doc)
#     return doc

# def normalize_dates(data):
#     """Convert date/datetime objects into ISO strings recursively"""
#     for key, value in data.items():
#         if isinstance(value, date) and not isinstance(value, datetime):
#             data[key] = value.isoformat()
#         elif isinstance(value, datetime):
#             data[key] = value.isoformat()
#         elif isinstance(value, dict):
#             normalize_dates(value)
#         elif isinstance(value, list):
#             for i, v in enumerate(value):
#                 if isinstance(v, (date, datetime)):
#                     data[key][i] = v.isoformat()
#                 elif isinstance(v, dict):
#                     normalize_dates(v)
#     return data

# # ------------------- Endpoints -------------------

# @csrf_exempt
# @api_view(['POST'])
# def create_college_in(request):
#     """Create a new CollegeIN record"""
#     try:
#         data = request.data
#         mapped_data = {
#             'college_category': data.get('collegeCategory'),
#             'vendor_id': data.get('vendor_id'),
#             'date': data.get('date'),
#             'invoice_no': data.get('invoiceNo'),
#             'invoice_date': data.get('invoiceDate'),
#             'credit_period': data.get('creditPeriod'),
#             'due_date': data.get('dueDate'),
#             'payment_mode': data.get('paymentMode'),
#             'items': json.dumps(data.get('items', [])),
#             'created_by': data.get('auth-user-id', 'Anonymous'),
#             'is_active': True,
#             'created_date': timezone.now().isoformat(),
#         }

#         # Summary / numeric fields
#         summary = data.get('summary', {})
#         summary_mapping = {
#             'non_taxable_amount': 'nonTaxableAmount',
#             'taxable_amount': 'taxableAmount',
#             'tax_paid_to_supplier': 'taxPaidToSupplier',
#             'local_tax': 'localTax',
#             'remarks': 'remarks',
#             'cgst': 'cgst',
#             'sgst': 'sgst',
#             'igst': 'igst',
#             'cess': 'cess',
#             'central_sales_tax': 'centralSalesTax',
#             'round_amount': 'roundAmount',
#             'total_amount': 'totalAmount',
#             'tax_on_free_items': 'taxOnFreeItems',
#             'total_discount': 'totalDiscount',
#             'net_invoice_amount': 'netInvoiceAmount',
#             'quotation_rate': 'quotationRate',
#             'courier_transport_charge': 'courierTransportCharge',
#         }

#         for backend_field, frontend_field in summary_mapping.items():
#             mapped_data[backend_field] = Decimal128(str(summary.get(frontend_field, 0)))

#         # Initialize payment status
#         total_amount = convert_decimal128_to_float(mapped_data.get('total_amount'))
#         mapped_data['payment_status'] = [{
#             'status': 'Not Paid',
#             'amount_paid': 0.0,
#             'pending_amount': total_amount,
#             'payment_method': None,
#             'payment_details': None,
#             'paid_by': None,
#             'timestamp': timezone.now().isoformat()
#         }]
#         mapped_data['overall_payment_status'] = 'Not Paid'
#         mapped_data['total_amount_paid'] = Decimal128('0.0')

#         # Insert into MongoDB
#         inserted = collection.insert_one(mapped_data)
#         mapped_data['_id'] = str(inserted.inserted_id)

#         return Response({
#             'status': 'success',
#             'message': 'CollegeIN record created successfully',
#             'data': clean_mongo_document(mapped_data)
#         }, status=201)

#     except Exception as e:
#         logger.error(f"Error in create_college_in: {str(e)}\n{traceback.format_exc()}")
#         return Response({'status': 'error', 'message': str(e)}, status=500)


# @api_view(['GET'])
# def get_college_in_list(request):
#     """Get list of CollegeIN records with pagination"""
#     try:
#         page = int(request.GET.get('page', 1))
#         page_size = int(request.GET.get('page_size', 10))

#         all_records = list(collection.find({"is_active": True}).sort("created_date", -1))
#         total_records = len(all_records)
#         total_pages = (total_records + page_size - 1) // page_size

#         start = (page - 1) * page_size
#         end = start + page_size
#         page_records = all_records[start:end]

#         cleaned_records = [clean_mongo_document(doc) for doc in page_records]

#         return Response({
#             'status': 'success',
#             'data': cleaned_records,
#             'pagination': {
#                 'current_page': page,
#                 'total_pages': total_pages,
#                 'total_records': total_records,
#                 'has_next': page < total_pages,
#                 'has_previous': page > 1
#             }
#         }, status=200)

#     except Exception as e:
#         logger.error(f"Error in get_college_in_list: {str(e)}\n{traceback.format_exc()}")
#         return Response({'status': 'error', 'message': str(e)}, status=500)


# @api_view(['GET'])
# def college_in_detail(request, record_id):
#     """Get CollegeIN record by ID"""
#     try:
#         doc = collection.find_one({"_id": ObjectId(record_id), "is_active": True})
#         if not doc:
#             return Response({'status': 'error', 'message': 'Record not found'}, status=404)

#         # Parse items
#         items = doc.get('items', [])
#         if isinstance(items, str):
#             try:
#                 doc['items'] = json.loads(items)
#             except json.JSONDecodeError:
#                 doc['items'] = []

#         # Convert numeric fields
#         for item in doc.get('items', []):
#             for field in ['itemValue', 'unitPrice', 'tax', 'cgstAmt', 'sgstAmt', 'mrp']:
#                 if field in item:
#                     item[field] = convert_decimal128_to_float(item[field])

#         return Response({'status': 'success', 'data': clean_mongo_document(doc)}, status=200)

#     except Exception as e:
#         logger.error(f"Error in college_in_detail: {str(e)}\n{traceback.format_exc()}")
#         return Response({'status': 'error', 'message': str(e)}, status=500)


# @api_view(['PATCH'])
# def update_college_in(request, record_id):
#     """Update CollegeIN record by ID"""
#     try:
#         data = request.data
#         update_data = {k: v for k, v in data.items() if v is not None}
#         update_data['lastmodified_date'] = timezone.now().isoformat()

#         # Convert numeric summary fields to Decimal128
#         numeric_fields = [
#             'non_taxable_amount', 'taxable_amount', 'tax_paid_to_supplier',
#             'local_tax', 'cgst', 'sgst', 'igst', 'cess', 'central_sales_tax',
#             'round_amount', 'total_amount', 'tax_on_free_items', 'total_discount',
#             'net_invoice_amount', 'quotation_rate', 'courier_transport_charge',
#             'total_amount_paid'
#         ]
#         for field in numeric_fields:
#             if field in update_data:
#                 update_data[field] = Decimal128(str(update_data[field]))

#         result = collection.update_one(
#             {"_id": ObjectId(record_id), "is_active": True},
#             {"$set": update_data}
#         )
#         if result.modified_count == 1:
#             updated_doc = collection.find_one({"_id": ObjectId(record_id)})
#             return Response({'status': 'success', 'data': clean_mongo_document(updated_doc)}, status=200)
#         return Response({'status': 'error', 'message': 'Update failed'}, status=400)

#     except Exception as e:
#         logger.error(f"Error in update_college_in: {str(e)}\n{traceback.format_exc()}")
#         return Response({'status': 'error', 'message': str(e)}, status=500)


# @api_view(['PATCH'])
# def delete_college_in(request, record_id):
#     """Soft delete CollegeIN record"""
#     try:
#         result = collection.update_one(
#             {"_id": ObjectId(record_id), "is_active": True},
#             {"$set": {"is_active": False, "lastmodified_date": timezone.now().isoformat()}}
#         )
#         if result.modified_count == 1:
#             return Response({'status': 'success', 'message': 'Record deleted'}, status=200)
#         return Response({'status': 'error', 'message': 'Record not found'}, status=404)

#     except Exception as e:
#         logger.error(f"Error in delete_college_in: {str(e)}\n{traceback.format_exc()}")
#         return Response({'status': 'error', 'message': str(e)}, status=500)
