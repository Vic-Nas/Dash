from django.contrib import admin
from .models import GlobalChatMessage, DirectMessage


@admin.register(GlobalChatMessage)
class GlobalChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'createdAt')
    list_filter = ('createdAt',)
    search_fields = ('user__username', 'message')
    readonly_fields = ('createdAt',)


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'recipient', 'message', 'isRead', 'createdAt')
    list_filter = ('isRead', 'createdAt')
    search_fields = ('sender__username', 'recipient__username', 'message')
    readonly_fields = ('createdAt',)