
from django.urls import path
from .views import HomeView, update_appearance

app_name = 'core'

urlpatterns = [
    path('', HomeView.as_view(), name='home'),
    path('appearance/', update_appearance, name='update_appearance'),
]
