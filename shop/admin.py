from django.contrib import admin
from .models import CoinPackage, CoinPurchase, Transaction, SystemSettings


@admin.register(CoinPackage)
class CoinPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "coins", "price", "isActive", "displayOrder")
    list_filter = ("isActive",)
    search_fields = ("name",)


@admin.register(CoinPurchase)
class CoinPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "package", "status", "pricePaid", "createdAt")
    list_filter = ("status",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "transactionType", "createdAt")
    list_filter = ("transactionType",)


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ("settingKey", "settingValue", "description", "updatedAt")
    search_fields = ("settingKey", "description")
    
    def get_readonly_fields(self, request, obj=None):
        # Make key readonly when editing existing settings
        if obj:
            return ["settingKey"]
        return []