from django.urls import path
from . import views

urlpatterns = [
    path('solo/', views.solo, name='solo'),
    path('save-solo-run/', views.saveSoloRun, name='saveSoloRun'),
    path('multiplayer/', views.multiplayer, name='multiplayer'),
    path('join-match/', views.joinMatch, name='joinMatch'),
    path('lobby/<int:matchId>/', views.lobby, name='lobby'),
    path('leave-lobby/', views.leaveLobby, name='leaveLobby'),  # ADDED THIS LINE
]