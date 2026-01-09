from django.contrib import admin
from .models import playerScore


@admin.register(playerScore)
class playerScoreAdmin(admin.ModelAdmin):
    list_display = ("playerName", "scoreValue", "createdAt")
    search_fields = ("playerName",)
    list_filter = ("createdAt",)
    ordering = ("-scoreValue", "createdAt")
