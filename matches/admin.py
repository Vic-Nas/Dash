from django.contrib import admin
from .models import matchType, match, matchParticipation, gameState, soloRun

@admin.register(matchType)
class matchTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "entryFee", "gridSize", "speed", "playersRequired", "isActive")
    list_filter = ("isActive", "speed")
    search_fields = ("name",)

@admin.register(match)
class matchAdmin(admin.ModelAdmin):
    list_display = ("id", "matchType", "status", "gridSize", "currentPlayers", "totalPot", "createdAt")
    list_filter = ("status", "isSoloMode")

@admin.register(matchParticipation)
class matchParticipationAdmin(admin.ModelAdmin):
    list_display = ("match", "player", "entryFeePaid", "livesRemaining", "placement")
    list_filter = ("placement",)

@admin.register(gameState)
class gameStateAdmin(admin.ModelAdmin):
    list_display = ("match", "tickNumber", "timestamp", "activePlayers")

@admin.register(soloRun)
class soloRunAdmin(admin.ModelAdmin):
    list_display = ("player", "wallsSurvived", "netCoins", "startedAt", "endedAt")
