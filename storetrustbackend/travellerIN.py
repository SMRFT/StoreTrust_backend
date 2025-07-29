from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
import json
from .models import TravellersIN
from .serializers import TravellersINSerializer
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import TravellerIntent
from .serializers import TravellerIntentSerializer

@csrf_exempt
@require_http_methods(["POST"])
def create_travellers_in(request):
    """
    Create a new TravellersIN record
    """
    try:
        data = json.loads(request.body)
        
        # Map frontend field names to backend field names
        mapped_data = {
            'purchase_category': data.get('purchaseCategory'),
            'vendor': data.get('vendor'),
            'date': data.get('date'),
            'supplier_address': data.get('supplierAddress'),
            'contact_person': data.get('contactPerson'),
            'phone': data.get('phone'),
            'invoice_no': data.get('invoiceNo'),
            'invoice_date': data.get('invoiceDate'),
            'credit_period': data.get('creditPeriod'),
            'due_date': data.get('dueDate'),
            'reference': data.get('reference'),
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
        
        # Add audit fields
        mapped_data['created_by'] = request.user.username if request.user.is_authenticated else 'Anonymous'
        
        serializer = TravellersINSerializer(data=mapped_data)
        if serializer.is_valid():
            travellers_in = serializer.save()
            return JsonResponse({
                'status': 'success',
                'message': 'TravellersIN record created successfully',
                'data': TravellersINSerializer(travellers_in).data
            }, status=201)
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@require_http_methods(["GET"])
def get_travellers_in_list(request):
    """
    Get list of TravellersIN records with pagination
    """
    try:
        travellers_in_list = TravellersIN.objects.all().order_by('-created_date')
        
        # Pagination
        page = request.GET.get('page', 1)
        page_size = request.GET.get('page_size', 10)
        
        paginator = Paginator(travellers_in_list, page_size)
        page_obj = paginator.get_page(page)
        
        serializer = TravellersINSerializer(page_obj.object_list, many=True)
        
        return JsonResponse({
            'status': 'success',
            'data': serializer.data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_records': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@require_http_methods(["GET"])
def get_travellers_in_detail(request, pk):
    """
    Get specific TravellersIN record by ID
    """
    try:
        travellers_in = TravellersIN.objects.get(pk=pk)
        serializer = TravellersINSerializer(travellers_in)
        
        return JsonResponse({
            'status': 'success',
            'data': serializer.data
        })
        
    except TravellersIN.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'TravellersIN record not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["PUT"])
def update_travellers_in(request, pk):
    """
    Update specific TravellersIN record
    """
    try:
        travellers_in = TravellersIN.objects.get(pk=pk)
        data = json.loads(request.body)
        
        # Map frontend field names to backend field names (same as create)
        mapped_data = {
            'purchase_category': data.get('purchaseCategory'),
            'vendor': data.get('vendor'),
            'date': data.get('date'),
            'supplier_address': data.get('supplierAddress'),
            'contact_person': data.get('contactPerson'),
            'phone': data.get('phone'),
            'invoice_no': data.get('invoiceNo'),
            'invoice_date': data.get('invoiceDate'),
            'credit_period': data.get('creditPeriod'),
            'due_date': data.get('dueDate'),
            'reference': data.get('reference'),
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
        
        # Add audit fields
        mapped_data['lastmodified_by'] = request.user.username if request.user.is_authenticated else 'Anonymous'
        mapped_data['lastmodified_date'] = timezone.now()
        
        serializer = TravellersINSerializer(travellers_in, data=mapped_data, partial=True)
        if serializer.is_valid():
            updated_travellers_in = serializer.save()
            return JsonResponse({
                'status': 'success',
                'message': 'TravellersIN record updated successfully',
                'data': TravellersINSerializer(updated_travellers_in).data
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Validation failed',
                'errors': serializer.errors
            }, status=400)
            
    except TravellersIN.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'TravellersIN record not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_travellers_in(request, pk):
    """
    Delete specific TravellersIN record
    """
    try:
        travellers_in = TravellersIN.objects.get(pk=pk)
        travellers_in.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': 'TravellersIN record deleted successfully'
        })
        
    except TravellersIN.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'TravellersIN record not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
    
@api_view(['GET', 'POST'])
def travellers_intent(request):
    if request.method == 'GET':
        items = TravellerIntent.objects.all()
        serializer = TravellerIntentSerializer(items, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = TravellerIntentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)