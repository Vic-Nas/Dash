from django.db import models
from django.contrib.auth import get_user_model


class GlobalChatMessage(models.Model):
    """Simple global chat visible to all users"""
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='globalMessages')
    message = models.TextField(max_length=500)
    createdAt = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-createdAt']
    
    def __str__(self):
        return f"{self.user.username}: {self.message[:50]}"


class DirectMessage(models.Model):
    """Direct messages between two users"""
    sender = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='sentMessages')
    recipient = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='receivedMessages')
    message = models.TextField(max_length=1000)
    isRead = models.BooleanField(default=False)
    createdAt = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-createdAt']
    
    def __str__(self):
        return f"{self.sender.username} → {self.recipient.username}"