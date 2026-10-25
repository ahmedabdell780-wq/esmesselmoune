from django.urls import path
from . import views

app_name = 'clubs'

urlpatterns = [
    path('', views.ClubDashboardView.as_view(), name='dashboard'),
    path('players/', views.PlayerListView.as_view(), name='player_list'),
    path('players/<int:pk>/', views.PlayerDetailView.as_view(), name='player_detail'),
    path('players/cards/', views.PlayerCardsPrintView.as_view(), name='player_cards_print'),
    path('players/print/', views.PlayerListPrintView.as_view(), name='player_list_print'),
    path('players/simple-print/', views.PlayerSimpleListPrintView.as_view(), name='player_simple_list_print'),
    
    # Create actions
    path('category/add/', views.CategoryCreateView.as_view(), name='category_add'),
    path('category/<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_edit'),
    path('category/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    path('players/add/', views.ClubPlayerCreateView.as_view(), name='player_add'),
    path('players/check-duplicate/', views.CheckDuplicatePlayerView.as_view(), name='player_check_duplicate'),
    path('players/<int:pk>/edit/', views.ClubPlayerUpdateView.as_view(), name='player_edit'),
    path('players/<int:pk>/delete/', views.ClubPlayerDeleteView.as_view(), name='player_delete'),
    path('trainings/add/', views.TrainingSessionCreateView.as_view(), name='training_add'),
    path('matches/add/', views.ClubMatchCreateView.as_view(), name='match_add'),
    path('settings/', views.ClubSettingsUpdateView.as_view(), name='settings'),
    
    # New features
    path('staff/', views.StaffListView.as_view(), name='staff_list'),
    path('staff/print/', views.StaffListPrintView.as_view(), name='staff_list_print'),
    path('staff/add/', views.StaffCreateView.as_view(), name='staff_add'),
    path('staff/<int:pk>/edit/', views.StaffUpdateView.as_view(), name='staff_edit'),
    path('staff/<int:pk>/delete/', views.StaffDeleteView.as_view(), name='staff_delete'),
    path('subscriptions/add/', views.SubscriptionCreateView.as_view(), name='subscription_add'),
    path('subscriptions/<int:pk>/edit/', views.SubscriptionUpdateView.as_view(), name='subscription_edit'),
    path('subscriptions/<int:pk>/delete/', views.SubscriptionDeleteView.as_view(), name='subscription_delete'),
    path('medical/add/', views.MedicalRecordCreateView.as_view(), name='medical_add'),
    path('evaluations/add/', views.PlayerEvaluationCreateView.as_view(), name='evaluation_add'),
    path('players/<int:player_id>/equipment/', views.PlayerEquipmentUpdateView.as_view(), name='equipment_edit'),
    
    # Public Academy Registration
    path('academy/register/', views.AcademyRegistrationView.as_view(), name='academy_register'),
    path('academy/player/<int:pk>/print/', views.AcademyRegistrationPrintView.as_view(), name='academy_print_form'),
    
    # Standings & Results Poster Generator
    path('standings-generator/', views.StandingsGeneratorView.as_view(), name='standings_generator'),
    
    # Player Passports (Passeport du Joueur - Ligue Wilaya Tipaza)
    path('players/<int:pk>/passport/', views.PlayerPassportView.as_view(), name='player_passport'),
    path('players/passports/', views.PlayerPassportCategoryListView.as_view(), name='player_passport_list'),
    path('players/passports/print/', views.PlayerPassportBatchPrintView.as_view(), name='player_passport_batch_print'),
    
    # Official League Forms (FAF Connect - Ligue de Tipaza)
    path('players/<int:pk>/license-form/', views.PlayerLicenseFormView.as_view(), name='player_license_form'),
    path('players/<int:pk>/medical-certificate/', views.PlayerMedicalCertificateView.as_view(), name='player_medical_certificate'),
    path('forms/license-form/print/', views.PlayerLicenseFormBatchPrintView.as_view(), name='license_form_batch_print'),
    path('forms/medical-certificate/print/', views.PlayerMedicalCertificateBatchPrintView.as_view(), name='medical_certificate_batch_print'),
    path('forms/blank/license-form/', views.BlankLicenseFormView.as_view(), name='blank_license_form'),
    path('forms/blank/medical-certificate/', views.BlankMedicalCertificateView.as_view(), name='blank_medical_certificate'),
    
    # Anti-Doping Medical Clearance (الكشف عن تعاطي المخدرات - التحاليل الطبية السلبية)
    path('players/<int:pk>/anti-doping/', views.PlayerAntiDopingView.as_view(), name='player_anti_doping'),
    path('staff/<int:pk>/anti-doping/', views.StaffAntiDopingView.as_view(), name='staff_anti_doping'),
    path('forms/anti-doping/print/', views.AntiDopingBatchPrintView.as_view(), name='anti_doping_batch_print'),
    path('staff/anti-doping/print/', views.StaffAntiDopingBatchPrintView.as_view(), name='staff_anti_doping_batch_print'),
    path('forms/blank/anti-doping/', views.BlankAntiDopingView.as_view(), name='blank_anti_doping'),

    # Staff Medical Certificate (شهادة الأهلية الطبية للمدربين والطاقم)
    path('staff/<int:pk>/medical-certificate/', views.StaffMedicalCertificateView.as_view(), name='staff_medical_certificate'),
    path('staff/medical-certificate/print/', views.StaffMedicalCertificateBatchPrintView.as_view(), name='staff_medical_certificate_batch_print'),
    path('forms/blank/staff-medical-certificate/', views.BlankStaffMedicalCertificateView.as_view(), name='blank_staff_medical_certificate'),

    # League & Generator & Public Views
    path('test-matches/', views.test_matches_view, name='test_matches'),
    path('debug-matches/', views.debug_matches, name='debug_matches'),
    path('setup-league/', views.populate_league_view, name='setup_league'),
    path('generator/', views.GeneratorView.as_view(), name='generator'),
    path('schedule/', views.LeagueScheduleView.as_view(), name='league_schedule'),
    path('matches/', views.PublicMatchListView.as_view(), name='public_matches'),
    path('categories/', views.PublicCategoryListView.as_view(), name='public_categories'),
    path('coach-dashboard/', views.CoachDashboardView.as_view(), name='coach_dashboard'),
    path('parent-dashboard/', views.ParentDashboardView.as_view(), name='parent_dashboard'),
    path('attendance/take/<int:session_id>/', views.TakeAttendanceView.as_view(), name='take_attendance'),
    path('attendance/', views.TrainingAttendanceListView.as_view(), name='attendance_list'),
    path('medical/', views.MedicalRecordListView.as_view(), name='medical_list'),
    path('evaluations/', views.PlayerEvaluationListView.as_view(), name='evaluation_list'),
    path('equipment/', views.PlayerEquipmentListView.as_view(), name='equipment_list'),
    path('subscriptions/', views.SubscriptionListView.as_view(), name='subscription_list'),
    path('news/', views.NewsListView.as_view(), name='news_list'),
    path('news/<slug:slug>/', views.NewsDetailView.as_view(), name='news_detail'),

    # Advanced Attendance Tracking Module
    path('sessions/', views.SessionListView.as_view(), name='session_list'),
    path('sessions/create/', views.SessionCreateView.as_view(), name='session_create'),
    path('sessions/<int:pk>/sheet/', views.SessionAttendanceSheetView.as_view(), name='session_sheet'),
    path('sessions/<int:session_pk>/record/<int:player_pk>/', views.AttendanceRecordHTMXView.as_view(), name='attendance_record'),
    path('sessions/<int:session_pk>/mark-all-present/', views.AttendanceMarkAllPresentHTMXView.as_view(), name='attendance_mark_all_present'),
    path('sessions/stats/', views.AttendanceStatsView.as_view(), name='attendance_stats'),

    # Guardian Portal & Announcements
    path('guardian/portal/', views.GuardianPortalView.as_view(), name='guardian_portal'),
    path('announcements/', views.AnnouncementListView.as_view(), name='announcement_list'),
    path('announcements/create/', views.AnnouncementCreateView.as_view(), name='announcement_create'),
    path('announcements/<int:pk>/', views.AnnouncementDetailView.as_view(), name='announcement_detail'),

]
