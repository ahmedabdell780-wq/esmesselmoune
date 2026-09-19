from django.urls import path
from .views import InjuryViewSet

urlpatterns = [
    path('injuries/',      InjuryViewSet.as_view({'get': 'list', 'post': 'create'}),        name='api-injuries'),
    path('injuries/<int:pk>/', InjuryViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='api-injury-detail'),
]
