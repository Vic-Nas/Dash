from django.urls import path
from . import views

urlpatterns = [
    path('global/', views.globalChat, name='globalChat'),
    path('global/poll/', views.pollGlobalMessages, name='pollGlobalMessages'),
    path('global/send/', views.sendGlobalMessage, name='sendGlobalMessage'),
    path('messages/', views.directMessages, name='directMessages'),
    path('messages/<int:userId>/', views.conversation, name='conversation'),
    path('messages/send/', views.sendDirectMessage, name='sendDirectMessage'),
    path('messages/unread/', views.unreadCount, name='unreadCount'),
]