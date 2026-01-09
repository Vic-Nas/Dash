from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/match/<int:matchId>/', consumers.GameConsumer.as_asgi()),
]