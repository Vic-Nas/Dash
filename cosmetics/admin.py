from django.contrib import admin
from .models import BotSkin, OwnedSkin

@admin.register(BotSkin)
class BotSkinAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "rarity", "isDefault", "displayOrder")
    list_filter = ("rarity", "isDefault")
    search_fields = ("name",)

@admin.register(OwnedSkin)
class OwnedSkinAdmin(admin.ModelAdmin):
    list_display = ("player", "skin", "purchasedAt")
