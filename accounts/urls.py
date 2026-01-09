from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', views.customLogout, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/upload/', views.uploadProfilePicture, name='uploadProfilePicture'),
    path('profile/search/', views.profileSearch, name='profileSearch'),
    path('profile/<str:username>/', views.publicProfile, name='publicProfile'),
]