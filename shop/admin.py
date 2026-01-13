from django.contrib import admin
from .models import CoinPackage, CoinPurchase, Transaction, SystemSettings


@admin.register(CoinPackage)
class CoinPackageAdmin(admin.ModelAdmin):
    list_display = ['name', 'coins', 'price', 'displayOrder', 'isActive']
    list_editable = ['displayOrder', 'isActive']
    ordering = ['displayOrder', 'name']


@admin.register(CoinPurchase)
class CoinPurchaseAdmin(admin.ModelAdmin):
    list_display = ['user', 'package', 'coinAmount', 'pricePaid', 'status', 'createdAt']
    list_filter = ['status', 'createdAt']
    search_fields = ['user__username', 'stripePaymentIntentId']
    readonly_fields = ['stripePaymentIntentId', 'createdAt', 'completedAt']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'transactionType', 'description', 'createdAt']
    list_filter = ['transactionType', 'createdAt']
    search_fields = ['user__username', 'description']
    readonly_fields = ['createdAt']


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ['settingKey', 'settingValue', 'description', 'updatedAt']
    search_fields = ['settingKey', 'description']
    readonly_fields = ['updatedAt']
    
    fieldsets = (
        ('Setting', {
            'fields': ('settingKey', 'settingValue')
        }),
        ('Documentation', {
            'fields': ('description', 'updatedAt')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields + ['settingKey']
        return self.readonly_fields