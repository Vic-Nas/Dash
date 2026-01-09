from django.contrib import admin
from .models import profile

@admin.register(profile)
class profileAdmin(admin.ModelAdmin):
    list_display = ("user", "coins", "soloHighScore", "totalWins", "isActive", "createdAt")
    search_fields = ("user__username",)
