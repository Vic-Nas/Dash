from django.contrib import admin
from .models import CoinPackage, CoinPurchase, Transaction, SystemSettings

@admin.register(CoinPackage)
class CoinPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "coins", "price", "isActive", "displayOrder")
    list_filter = ("isActive",)

@admin.register(CoinPurchase)
class CoinPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "package", "status", "coinAmount", "pricePaid", "createdAt")
    list_filter = ("status",)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "transactionType", "description", "createdAt")
    list_filter = ("transactionType",)

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ("settingKey", "settingValue", "description", "updatedAt")
    search_fields = ("settingKey", "description")
    
    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ('settingKey',)
        return ()