from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/',    views.LoginView.as_view(),                                            name='login'),
    path('logout/',   auth_views.LogoutView.as_view(),                                      name='logout'),
    path('register/', views.RegisterView.as_view(),                                         name='register'),
    path('profile/',  views.ProfileView.as_view(),                                          name='profile'),
    path('appearance/', views.AppearanceView.as_view(),                                     name='appearance'),
    path('pending/',    views.PendingUserListView.as_view(),                                name='pending_users'),
    path('approve/<int:pk>/', views.UserApprovalActionView.as_view(),                       name='approve_user'),
]
