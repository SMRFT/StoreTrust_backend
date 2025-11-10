from django.urls import path
from . import travellerIN, inventory
from . import views
urlpatterns = [
    # TravellersIN (GRN Generation):
    path('inventory/check-stock/', inventory.stock_alerts, name='stock_alerts'),
    path('travellers-in/', travellerIN.create_travellers_in, name='create_travellers_in'),
    path('travellers-in/list/', travellerIN.get_travellers_in_list, name='get_travellers_in_list'),    
    path('travellers-in/previous-purchases/', travellerIN.get_previous_purchases, name='previous_purchases'),
    path('travellers-in/update/<path:grn_number>/', travellerIN.travellers_in_update, name='travellers_in_update'),
    path('travellers-in/delete/', travellerIN.delete_grn_record, name='delete_grn_record'),

    # TravellersIN Intent:
    path('travellers-intent/', travellerIN.travellers_intent, name='travellers_intent'),
    path('travellers-intent/update-item/', travellerIN.update_intent_item, name='update_intent_item'),
    path('travellers-intent/by-date-range/', travellerIN.get_travellers_intent_by_date_range, name='travellers_intent_by_date_range'),
    
    
        
    # Vendor URLs
    path('vendors/', inventory.create_vendor, name='create_vendor'),
    path('vendors/list/', inventory.list_vendors, name='list_vendors'),
    path("get_vendors/", inventory.get_vendors, name="get_vendors"),
    path("vendors/update/<str:vendor_id>/", inventory.update_vendor, name="update_vendor"),
    path("delete_vendor/<str:vendor_id>/", inventory.delete_vendor, name="delete_vendor"),
    
    # Item URLs
    path('items/', inventory.create_item, name='create_item'),
    path('items/list/', inventory.list_items, name='list_items'),
    path('items/groups/', inventory.get_groups, name='get_groups'),
    path('items/categories/', inventory.get_categories, name='get_categories'),
    path('items/classifications/', inventory.get_classifications, name='get_classifications'),
    path('get_items/', inventory.get_items, name='get_items'),
    path('update_item/<str:item_id>/', inventory.update_item, name='update_item'),
    path('delete_item/<str:item_id>/', inventory.delete_item, name='delete_item'),

    
    # Traveller Intent:
    path('travellers-intent/soft-delete-item/', travellerIN.soft_delete_intent_item),
    path('travellers-in/<str:grn_number>/', travellerIN.travellers_in_detail, name='travellers_in_detail'),
    path('travellers-intent/soft-delete-intent/', travellerIN.soft_delete_intent, name='soft_delete_intent'),
    path("travellers-intent/soft-delete-item/", travellerIN.soft_delete_intent, name="soft_delete_intent_item"),

    # Traveller Intent Report:
    path('travellers-stock/', travellerIN.travellers_stock, name='travellers_stock'),
   ]