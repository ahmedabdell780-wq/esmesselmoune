from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('mark-read/<int:pk>/', views.MarkNotificationReadView.as_view(), name='mark_read'),
    path('mark-all-read/', views.MarkAllReadView.as_view(), name='mark_all_read'),
]
