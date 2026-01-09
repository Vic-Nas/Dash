from django.db import models
from django.contrib.auth import get_user_model


class BotSkin(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    previewImage = models.ImageField(upload_to='skins/previews/', null=True, blank=True)
    colorPrimary = models.CharField(max_length=7)
    colorSecondary = models.CharField(max_length=7, null=True, blank=True)
    trailEffect = models.CharField(max_length=16, null=True, blank=True, choices=[
        ('NONE', 'NONE'), ('GLOW', 'GLOW'), ('SPARKLE', 'SPARKLE'), ('FIRE', 'FIRE'), ('ICE', 'ICE')
    ])
    price = models.DecimalField(max_digits=12, decimal_places=2)
    isDefault = models.BooleanField(default=False)
    rarity = models.CharField(max_length=16, choices=[
        ('COMMON', 'COMMON'), ('RARE', 'RARE'), ('EPIC', 'EPIC'), ('LEGENDARY', 'LEGENDARY')
    ])
    displayOrder = models.IntegerField(default=0)
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bot Skin'
        verbose_name_plural = 'Bot Skins'
        ordering = ['displayOrder', 'name']

    def __str__(self):
        return self.name


class OwnedSkin(models.Model):
    player = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='ownedSkins')
    skin = models.ForeignKey('cosmetics.BotSkin', on_delete=models.CASCADE, related_name='owners')
    purchasedAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('player', 'skin')
        verbose_name = 'Owned Skin'
        verbose_name_plural = 'Owned Skins'

    def __str__(self):
        return f"OwnedSkin({self.player}, {self.skin})"
