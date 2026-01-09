from django.contrib import admin
from .models import CoinPackage, CoinPurchase, Transaction

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
