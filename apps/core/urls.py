from django.urls import path
from .views import HomeView, category_matches

app_name = 'core'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('partials/matches/<str:category_name>/', category_matches, name='category_matches'),
]
