from django.contrib import admin
from .models import botSkin, ownedSkin

@admin.register(botSkin)
class botSkinAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "rarity", "isDefault", "displayOrder")
    list_filter = ("rarity", "isDefault")
    search_fields = ("name",)

@admin.register(ownedSkin)
class ownedSkinAdmin(admin.ModelAdmin):
    list_display = ("player", "skin", "purchasedAt")
