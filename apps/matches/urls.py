from django.urls import path
from . import views

app_name = 'matches'

urlpatterns = [
    path('',                    views.MatchCalendarView.as_view(), name='calendar'),
    path('<int:pk>/',           views.MatchDetailView.as_view(),   name='detail'),
    path('<int:pk>/sheet/',     views.MatchSheetView.as_view(),    name='match_sheet'),
    path('<int:pk>/score/',     views.EnterScoreView.as_view(),    name='enter_score'),
    path('<int:pk>/forfeit/',   views.SetForfeitView.as_view(),   name='set_forfeit'),
    path('<int:pk>/schedule/',  views.UpdateScheduleView.as_view(),name='update_schedule'),
    path('<int:pk>/add-goal/',  views.AddGoalView.as_view(),       name='add_goal'),
    path('<int:pk>/add-card/',  views.AddCardView.as_view(),       name='add_card'),
    path('<int:pk>/add-media/', views.AddMatchMediaView.as_view(), name='add_media'),
    path('media/<int:pk>/delete/', views.DeleteMatchMediaView.as_view(), name='delete_media'),
    path('<int:pk>/penalties/', views.UpdatePenaltiesView.as_view(),name='update_penalties'),
    path('<int:pk>/promo/',     views.MatchPromoView.as_view(),    name='promo'),
    path('<int:pk>/lineup/update/', views.UpdateLineupView.as_view(), name='update_lineup'),
    path('<int:pk>/lineup/remove/', views.RemoveFromLineupView.as_view(), name='remove_lineup'),
    path('process-cutout/',     views.ProcessCutoutView.as_view(), name='process_cutout'),
    path('<int:pk>/motm/',      views.ManOfTheMatchView.as_view(), name='motm'),
    path('<int:pk>/best-goalkeeper/', views.BestGoalkeeperView.as_view(), name='best_goalkeeper'),
    path('<int:pk>/referee-certificate/', views.RefereeCertificateView.as_view(), name='referee_certificate'),
    path('<int:pk>/referee-report/', views.RefereeReportView.as_view(), name='referee_report'),
    path('<int:pk>/honorary-certificate/', views.HonoraryCertificateView.as_view(), name='honorary_certificate'),
    path('<int:pk>/promo/save/',views.SavePromoConfigView.as_view(), name='save_promo_config'),
    path('<int:pk>/vote/',      views.MatchVoteView.as_view(),     name='vote'),
    path('<int:pk>/add-generic-event/', views.AddGenericEventView.as_view(), name='add_generic_event'),
    path('<int:pk>/update-live-timer/', views.UpdateLiveTimerView.as_view(), name='update_live_timer'),
    path('goals/<int:pk>/delete/',      views.DeleteGoalView.as_view(),       name='delete_goal'),
    path('goals/<int:pk>/edit/',        views.EditGoalView.as_view(),         name='edit_goal'),
    path('cards/<int:pk>/delete/',      views.DeleteCardView.as_view(),       name='delete_card'),
    path('cards/<int:pk>/edit/',        views.EditCardView.as_view(),         name='edit_card'),
    path('events/<int:pk>/delete/',     views.DeleteGenericEventView.as_view(), name='delete_event'),
    path('stats/',              views.StatsView.as_view(),         name='stats'),
]

