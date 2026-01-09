from django.contrib import admin
from .models import coinPackage, coinPurchase, transaction

@admin.register(coinPackage)
class coinPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "coins", "price", "isActive", "displayOrder")
    list_filter = ("isActive",)
    search_fields = ("name",)

@admin.register(coinPurchase)
class coinPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "package", "status", "pricePaid", "createdAt")
    list_filter = ("status",)

@admin.register(transaction)
class transactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "transactionType", "createdAt")
    list_filter = ("transactionType",)
