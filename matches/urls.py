from django.urls import path
from . import views

app_name = 'matches'

urlpatterns = [
    path('solo/', views.solo, name='solo'),
    path('progressive/', views.progressive, name='progressive'),
    path('save-solo-run/', views.saveSoloRun, name='saveSoloRun'),
    path('save-progressive-run/', views.saveProgressiveRun, name='saveProgressiveRun'),
    path('matchmaking/', views.matchmaking, name='matchmaking'),
    path('lobby/<int:matchId>/', views.lobby, name='lobby'),
    path('api/join-match/', views.joinMatch, name='joinMatch'),
    path('api/leave-lobby/', views.leaveLobby, name='leaveLobby'),
    path('api/force-start/', views.forceStart, name='forceStart'),
    path('api/check-activity/', views.checkActivity, name='checkActivity'),
    
    # Replay browser
    path('replays/', views.browseReplays, name='browseReplays'),
    path('replays/watch/', views.watchReplay, name='watchReplay'),
    path('replays/view/<str:replayType>/<int:replayId>/', views.replayViewer, name='replayViewer'),
]