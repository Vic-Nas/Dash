from django.db import models


class playerScore(models.Model):
    playerName = models.CharField(max_length=50)
    scoreValue = models.IntegerField(default=0)
    createdAt = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.playerName}: {self.scoreValue}"
