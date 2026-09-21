
from django.urls import path
from .views import HomeView, update_appearance, AboutUsView

app_name = 'core'

urlpatterns = [
    path('about/', AboutUsView.as_view(), name='about'),

    path('', HomeView.as_view(), name='home'),
    path('appearance/', update_appearance, name='update_appearance'),
]
