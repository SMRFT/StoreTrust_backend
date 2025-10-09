from django.urls import path
from . import travellerIN, inventory,collegeIN
from . import views

# from .collegeIN import college_intent, update_college_intent_item
# TODO: Implement these before enabling routes
# from .collegeIN import soft_delete_college_intent, soft_delete_college_intent_item, get_college_intent_by_date_range

urlpatterns = [
 # TravellersIN endpoints
    path('travellers-in/', travellerIN.create_travellers_in, name='create_travellers_in'),
    path('travellers-in/list/', travellerIN.get_travellers_in_list, name='get_travellers_in_list'),
    path('travellers-in/delete/', travellerIN.delete_grn_record, name='delete_grn_record'),
    path('travellers-in/update-payment-status/', travellerIN.update_payment_status, name='update_payment_status'),
    path('travellers-in/previous-purchases/', travellerIN.get_previous_purchases, name='previous_purchases'),
    path('travellers-intent/', travellerIN.travellers_intent, name='travellers_intent'),
    path('travellers-intent/update-item/',travellerIN.update_intent_item),
    path('travellers-intent/soft-delete-item/', travellerIN.soft_delete_intent_item),
    path('travellers-in/previous-purchases/', travellerIN.get_previous_purchases, name='previous_purchases'),
    # Endpoint to retrieve a specific TravellersIN record by GRN number
    path('travellers-in/<str:grn_number>/', travellerIN.travellers_in_detail, name='travellers_in_detail'),
    # Endpoint to update an existing TravellersIN record by GRN number
    path('travellers-in/<path:grn_number>/update/', travellerIN.travellers_in_update, name='travellers_in_update'),
    # Vendor URLs
    path('vendors/', inventory.create_vendor, name='create_vendor'),
    path('vendors/list/', inventory.list_vendors, name='list_vendors'),
    path('vendors/<int:vendor_id>/', inventory.get_vendor, name='get_vendor'),
    path('vendors/<int:vendor_id>/update/', inventory.update_vendor, name='update_vendor'),
    path('vendors/<int:vendor_id>/delete/', inventory.delete_vendor, name='delete_vendor'),
    
    # Item URLs
    path('items/', inventory.create_item, name='create_item'),
    path('items/list/', inventory.list_items, name='list_items'),
    path('items/<int:item_id>/', inventory.get_item, name='get_item'),
    path('items/<int:item_id>/update/', inventory.update_item, name='update_item'),
    path('items/<int:item_id>/delete/', inventory.delete_item, name='delete_item'),
    path('items/groups/', inventory.get_groups, name='get_groups'),
    path('items/categories/', inventory.get_categories, name='get_categories'),
    path('items/classifications/', inventory.get_classifications, name='get_classifications'),
    path('inventory/check-stock/', inventory.stock_alerts, name='stock_alerts'),
    # Traveller Intent endpoints
    path('travellers-intent/', travellerIN.travellers_intent, name='travellers_intent'),
    path('travellers-intent/update-item/', travellerIN.update_intent_item, name='update_intent_item'),
    path('travellers-intent/by-date-range/', travellerIN.get_travellers_intent_by_date_range, name='travellers_intent_by_date_range'),
    path('travellers-intent/soft-delete-intent/', travellerIN.soft_delete_intent, name='soft_delete_intent'),
    path("travellers-intent/soft-delete-item/", travellerIN.soft_delete_intent, name="soft_delete_intent_item"),
    path('item/list/', travellerIN.items_list, name='items_list'),
    path('items/list/', inventory.list_items, name='list_items'),
    path('travellers-stock/', travellerIN.travellers_stock, name='travellers_stock'),
    path('reduce_stock/', travellerIN.reduce_stock, name='reduce_stock'),
    # path('restore_stock/', travellerIN.restore_stock, name='restore_stock'),
    # path('add_back_stock/', travellerIN.add_back_stock, name='add_back_stock'),
    path('add_back_traveller_stock/', travellerIN.add_back_traveller_stock, name='add_back_traveller_stock'),
 
        # ===== vendors Endpoints =====
    path("get_vendors/", views.get_vendors, name="get_vendors"),
    path("vendors/create/", views.create_vendor, name="create_vendor"),
    path("vendors/update/<str:vendor_id>/", views.update_vendor, name="update_vendor"),
    path("delete_vendor/<str:vendor_id>/", views.delete_vendor, name="delete_vendor"),

        # ===== Items Endpoints =====
    path('get_items/', views.get_items, name='get_items'),               # GET all items
    path('create_item/', views.create_item, name='create_item'),         # POST new item
    path('update_item/<str:item_id>/', views.update_item, name='update_item'),  # PATCH item
    path('delete_item/<str:item_id>/', views.delete_item, name='delete_item'),  # DELETE item

    # College IN endpoints
#    path("college-intent/", collegeIN.college_intent, name="college_intent"),
    # path("college/intent/update/", collegeIN.update_college_intent_item, name="update_college_intent_item"),
    # path("college/intent/by-date-range/", collegeIN.get_college_intent_by_date_range, name="get_college_intent_by_date_range"),
    # path("college/intent/item/", collegeIN.college_intent, name="college_intent_item"),
    # path("college/intent/item/delete/", collegeIN. soft_delete_intent_item, name="soft_delete_intent_item"),
    # path("college/intent/delete/", collegeIN. soft_delete_intent, name="soft_delete_intent"),
    # path("college/intent/range/", collegeIN.get_college_intent_by_date_range, name="get_college_intent_by_date_range"),
    # path('item/list/', collegeIN.items_list, name='items_list'),
    # path('items/list/', inventory.list_items, name='list_items'),
    


    # mess intent endpoints
    # path('mess-intent/', messIN.mess_intent, name='mess_intent'),
    # path('mess-intent/update-item/', messIN.update_intent_item, name='update_intent_item'),
    # path('mess-intent/by-date-range/', messIN.get_mess_intent_by_date_range, name='mess_intent_by_date_range'),
    # path('mess-intent/soft-delete-intent/', messIN.soft_delete_intent, name='soft_delete_intent'),
    # path('item/list/', messIN.items_list, name='items_list'),
    # path('items/list/', inventory.list_items, name='list_items'),
    # path('mess-stock/', messIN.mess_stock, name='mess_stock'),
    # path('reduce_stock/', messIN.reduce_stock, name='reduce_stock'),
]