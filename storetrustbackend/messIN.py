from .serializers import MessIntentSerializer
from .models import MessIntent
from pyauth.auth import HasRolePermission
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
@api_view(['GET', 'POST'])
@permission_classes([HasRolePermission])
def Mess_intent(request):
    if request.method == 'GET':
        items = MessIntent.objects.all()
        serializer = MessIntentSerializer(items, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = MessIntentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)