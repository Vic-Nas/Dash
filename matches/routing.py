from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/match/<int:match_id>/', consumers.GameConsumer.as_asgi()),
]