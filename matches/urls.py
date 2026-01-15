from django.urls import path
from . import views

app_name = 'matches'

urlpatterns = [
    path('solo/', views.solo, name='solo'),
    path('progressive/', views.progressive, name='progressive'),
    path('save-solo-run/', views.saveSoloRun, name='saveSoloRun'),
    path('save-progressive-run/', views.saveProgressiveRun, name='saveProgressiveRun'),
    path('matchmaking/', views.matchmaking, name='matchmaking'),
    path('multiplayer/', views.matchmaking, name='multiplayer'),
    path('lobby/<int:matchId>/', views.lobby, name='lobby'),
    path('join-match/', views.joinMatch, name='joinMatch'),
    path('leave-lobby/', views.leaveLobby, name='leaveLobby'),
    path('force-start/', views.forceStart, name='forceStart'),
    path('check-auto-start/', views.checkAutoStart, name='checkAutoStart'),
    path('check-activity/', views.checkActivity, name='checkActivity'),
    
    # Replay browser
    path('replays/', views.browseReplays, name='browseReplays'),
    path('replays/watch/', views.watchReplay, name='watchReplay'),
    path('replays/view/<str:replayType>/<int:replayId>/', views.replayViewer, name='replayViewer'),
    
    # Private lobbies
    path('private/', views.privateLobbies, name='privateLobbies'),
    path('private/create/', views.createPrivateLobby, name='createPrivateLobby'),
    path('private/join/', views.joinPrivateLobby, name='joinPrivateLobby'),
    path('private/waiting/<int:lobby_id>/', views.privateWaiting, name='privateWaiting'),
    path('private/status/<int:lobby_id>/', views.privateStatus, name='privateStatus'),
    path('private/cancel/<int:lobby_id>/', views.cancelPrivateLobby, name='cancelPrivateLobby'),
]