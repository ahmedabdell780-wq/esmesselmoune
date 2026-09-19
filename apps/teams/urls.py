from django.urls import path
from . import views

app_name = 'teams'

urlpatterns = [
    # Teams
    path('',                      views.TeamListView.as_view(),          name='list'),
    path('ranking/',              views.GlobalRankingView.as_view(),     name='global_ranking'),
    path('create/',               views.TeamCreateView.as_view(),        name='create'),
    path('registration/',         views.TeamRegistrationView.as_view(),  name='registration'),
    path('<int:pk>/',             views.TeamDetailView.as_view(),        name='detail'),
    path('<int:pk>/edit/',        views.TeamUpdateView.as_view(),        name='edit'),
    path('<int:pk>/delete/',      views.TeamDeleteView.as_view(),        name='delete'),
    path('approval/',             views.TeamApprovalListView.as_view(),  name='approval_list'),
    path('approval/<int:pk>/',    views.TeamApprovalActionView.as_view(),name='approval_action'),

    # Players
    path('<int:team_pk>/players/',        views.PlayerListView.as_view(),   name='player_list'),
    path('<int:team_pk>/players/add/',    views.PlayerCreateView.as_view(), name='player_create'),
    path('<int:team_pk>/players/print/',  views.PlayerPrintView.as_view(),   name='player_print'),
    path('player/<int:pk>/',              views.PlayerDetailView.as_view(), name='player_detail'),
    path('player/<int:pk>/edit/',         views.PlayerUpdateView.as_view(), name='player_edit'),
    path('player/<int:pk>/delete/',       views.PlayerDeleteView.as_view(), name='player_delete'),
    path('player/<int:pk>/toggle-suspend/',views.PlayerToggleSuspendView.as_view(), name='player_toggle_suspend'),
    path('player/<int:pk>/toggle-captain/',views.PlayerToggleCaptainView.as_view(), name='player_toggle_captain'),

    # Search
    path('search/',               views.GlobalSearchView.as_view(),     name='search'),
    path('<int:pk>/lineup/', views.TeamLineupView.as_view(), name='lineup_manager'),
]
