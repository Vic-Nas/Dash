from django.contrib import admin
from .models import MatchType, Match, MatchParticipation, GameState, SoloRun, ProgressiveRun

@admin.register(MatchType)
class MatchTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "entryFee", "gridSize", "speed", "playersRequired", "hasBot", "isActive")
    list_filter = ("isActive", "speed", "hasBot")
    search_fields = ("name",)
    fieldsets = (
        ("Basic Info", {'fields': ('name', 'description', 'isActive', 'displayOrder')}),
        ("Game Settings", {'fields': ('gridSize', 'speed', 'wallSpawnInterval')}),
        ("Player Settings", {'fields': ('playersRequired', 'maxPlayers', 'entryFee')}),
        ("Bot Settings", {'fields': ('hasBot',)}),
    )

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ("id", "matchType", "status", "gridSize", "currentPlayers", "totalPot", "createdAt")
    list_filter = ("status", "isSoloMode")

@admin.register(MatchParticipation)
class MatchParticipationAdmin(admin.ModelAdmin):
    list_display = ("match", "get_player", "get_username", "entryFeePaid", "placement", "isBot")
    list_filter = ("placement", "isBot")
    
    def get_player(self, obj):
        return obj.player.username if obj.player else "—"
    get_player.short_description = "Player"
    
    def get_username(self, obj):
        return obj.username if obj.isBot else (obj.player.username if obj.player else "—")
    get_username.short_description = "Username"

@admin.register(GameState)
class GameStateAdmin(admin.ModelAdmin):
    list_display = ("match", "tickNumber", "timestamp", "activePlayers")

@admin.register(SoloRun)
class SoloRunAdmin(admin.ModelAdmin):
    list_display = ("player", "wallsSurvived", "netCoins", "startedAt", "endedAt")

@admin.register(ProgressiveRun)
class ProgressiveRunAdmin(admin.ModelAdmin):
    list_display = ("player", "level", "won", "botsEliminated", "coinsEarned", "startedAt")
    list_filter = ("won", "level")