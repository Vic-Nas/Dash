from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('guest-login/', views.guestLogin, name='guestLogin'),
    path('logout/', views.customLogout, name='logout'),
    path('settings/', views.accountSettings, name='accountSettings'),
    path('change-password/', views.changePassword, name='changePassword'),
    path('change-username/', views.changeUsername, name='changeUsername'),
    path('profile/upload/', views.uploadProfilePicture, name='uploadProfilePicture'),
    path('profile/search/', views.profileSearch, name='profileSearch'),
    path('profile/<str:username>/', views.publicProfile, name='publicProfile'),
]