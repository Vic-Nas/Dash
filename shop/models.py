from django.db import models
from django.contrib.auth import get_user_model


class coinPackage(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    coins = models.IntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    displayOrder = models.IntegerField(default=0)
    iconImage = models.ImageField(upload_to='shop/icons/', null=True, blank=True)
    isActive = models.BooleanField(default=True)
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['displayOrder', 'name']

    def __str__(self):
        return self.name


class coinPurchase(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='coinPurchases')
    package = models.ForeignKey('shop.coinPackage', on_delete=models.PROTECT, related_name='purchases')
    stripePaymentIntentId = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=16, choices=[('PENDING','PENDING'),('COMPLETED','COMPLETED'),('FAILED','FAILED'),('REFUNDED','REFUNDED')])
    coinAmount = models.IntegerField()
    pricePaid = models.DecimalField(max_digits=12, decimal_places=2)
    createdAt = models.DateTimeField(auto_now_add=True)
    completedAt = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"coinPurchase({self.user_id}, {self.package_id})"


class transaction(models.Model):
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transactionType = models.CharField(max_length=16, choices=[
        ('PURCHASE','PURCHASE'), ('MATCH_ENTRY','MATCH_ENTRY'), ('MATCH_WIN','MATCH_WIN'),
        ('SKIN_PURCHASE','SKIN_PURCHASE'), ('SOLO_REWARD','SOLO_REWARD'), ('SOLO_PENALTY','SOLO_PENALTY'),
        ('EXTRA_LIFE','EXTRA_LIFE'), ('REFUND','REFUND')
    ])
    relatedMatch = models.ForeignKey('matches.match', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    relatedSkin = models.ForeignKey('cosmetics.botSkin', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    description = models.CharField(max_length=255)
    balanceBefore = models.DecimalField(max_digits=12, decimal_places=2)
    balanceAfter = models.DecimalField(max_digits=12, decimal_places=2)
    createdAt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"transaction({self.user_id}, {self.amount})"
