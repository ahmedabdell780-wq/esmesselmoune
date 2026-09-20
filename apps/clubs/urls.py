from django.urls import path
from . import views

app_name = 'clubs'

urlpatterns = [
    path('', views.ClubDashboardView.as_view(), name='dashboard'),
    path('players/', views.PlayerListView.as_view(), name='player_list'),
    path('players/<int:pk>/', views.PlayerDetailView.as_view(), name='player_detail'),
    path('players/cards/', views.PlayerCardsPrintView.as_view(), name='player_cards_print'),
    path('players/print/', views.PlayerListPrintView.as_view(), name='player_list_print'),
    
    # Create actions
    path('category/add/', views.CategoryCreateView.as_view(), name='category_add'),
    path('category/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('category/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    path('players/add/', views.ClubPlayerCreateView.as_view(), name='player_add'),
    path('players/<int:pk>/edit/', views.ClubPlayerUpdateView.as_view(), name='player_edit'),
    path('players/<int:pk>/delete/', views.ClubPlayerDeleteView.as_view(), name='player_delete'),
    path('trainings/add/', views.TrainingSessionCreateView.as_view(), name='training_add'),
    path('matches/add/', views.ClubMatchCreateView.as_view(), name='match_add'),
    path('settings/', views.ClubSettingsUpdateView.as_view(), name='settings'),
    
    # New features
    path('staff/', views.StaffListView.as_view(), name='staff_list'),
    path('staff/add/', views.StaffCreateView.as_view(), name='staff_add'),
    
    # Phase 2
    path('subscriptions/', views.SubscriptionListView.as_view(), name='subscription_list'),
    path('parent-dashboard/', views.ParentDashboardView.as_view(), name='parent_dashboard'),

    path('subscriptions/add/', views.SubscriptionCreateView.as_view(), name='subscription_add'),
    path('subscriptions/<int:pk>/edit/', views.SubscriptionUpdateView.as_view(), name='subscription_edit'),
    path('subscriptions/<int:pk>/delete/', views.SubscriptionDeleteView.as_view(), name='subscription_delete'),
    path('medical/add/', views.MedicalRecordCreateView.as_view(), name='medical_add'),
    path('evaluations/add/', views.PlayerEvaluationCreateView.as_view(), name='evaluation_add'),
    path('players/<int:player_id>/equipment/', views.PlayerEquipmentUpdateView.as_view(), name='equipment_edit'),
    
    # Public Academy Registration
    path('academy/register/', views.AcademyRegistrationView.as_view(), name='academy_register'),
    path('academy/player/<int:pk>/print/', views.AcademyRegistrationPrintView.as_view(), name='academy_print_form'),

    path('news/', views.NewsListView.as_view(), name='news_list'),
    path('news/<slug:slug>/', views.NewsDetailView.as_view(), name='news_detail'),

]
