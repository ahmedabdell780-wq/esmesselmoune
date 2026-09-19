from django.urls import path
from . import views as api_views

urlpatterns = [
    path('standings/', api_views.TournamentViewSet.as_view({'get': 'standings'}), name='api-standings'),
]
