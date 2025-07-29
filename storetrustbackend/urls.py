from django.urls import path
from . import views,travellerIN

urlpatterns = [
    # TravellersIN endpoints
    path('travellers-in/', travellerIN.create_travellers_in, name='create_travellers_in'),
    path('travellers-in/list/', travellerIN.get_travellers_in_list, name='get_travellers_in_list'),
    path('travellers-in/<int:pk>/', travellerIN.get_travellers_in_detail, name='get_travellers_in_detail'),
    path('travellers-in/<int:pk>/update/', travellerIN.update_travellers_in, name='update_travellers_in'),
    path('travellers-in/<int:pk>/delete/', travellerIN.delete_travellers_in, name='delete_travellers_in'),
    path('travellers-intent/', travellerIN.travellers_intent, name='travellers_intent'),
]