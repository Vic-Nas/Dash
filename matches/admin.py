from django.contrib import admin
from .models import MatchType, Match, MatchParticipation, GameState, SoloRun

@admin.register(MatchType)
class MatchTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "entryFee", "gridSize", "speed", "playersRequired", "isActive")
    list_filter = ("isActive", "speed")
    search_fields = ("name",)

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("id", "matchType", "status", "gridSize", "currentPlayers", "totalPot", "createdAt")
    list_filter = ("status", "isSoloMode")

@admin.register(MatchParticipation)
class MatchParticipationAdmin(admin.ModelAdmin):
    list_display = ("match", "player", "entryFeePaid", "livesRemaining", "placement")
    list_filter = ("placement",)

@admin.register(GameState)
class GameStateAdmin(admin.ModelAdmin):
    list_display = ("match", "tickNumber", "timestamp", "activePlayers")

@admin.register(SoloRun)
class SoloRunAdmin(admin.ModelAdmin):
    list_display = ("player", "wallsSurvived", "netCoins", "startedAt", "endedAt")
