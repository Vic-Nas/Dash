from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import random
import string


class Profile(models.Model):
    user = models.OneToOneField(get_user_model(), on_delete=models.CASCADE, primary_key=True, related_name='profile')
    profilePic = models.ImageField(upload_to='dash/profiles/', null=True, blank=True)
    coins = models.DecimalField(max_digits=12, decimal_places=2, default=100)
    soloHighScore = models.IntegerField(default=0)
    totalWins = models.IntegerField(default=0)
    totalMatches = models.IntegerField(default=0)
    createdAt = models.DateTimeField(auto_now_add=True)
    isActive = models.BooleanField(default=True)
    activityLog = models.TextField(default="", blank=True)
    
    # New fields for anonymous auth system
    isAnonymous = models.BooleanField(default=True)
    hasChangedPassword = models.BooleanField(default=False)
    lastActivityAt = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'

    def __str__(self):
        return f"Profile({self.user})"


@receiver(post_save, sender=get_user_model())
def createProfile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)