from django.db import models
from django.contrib.auth import get_user_model


class MatchType(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    entryFee = models.DecimalField(max_digits=12, decimal_places=2)
    gridSize = models.IntegerField()
    speed = models.CharField(max_length=16, choices=[('SLOW', 'SLOW'), ('MEDIUM', 'MEDIUM'), ('FAST', 'FAST'), ('EXTREME', 'EXTREME')])
    playersRequired = models.IntegerField()
    maxPlayers = models.IntegerField()
    wallSpawnInterval = models.IntegerField(default=5)
    isActive = models.BooleanField(default=True)
    displayOrder = models.IntegerField(default=0)
    createdAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['displayOrder', 'name']

    def __str__(self):
        return self.name


class Match(models.Model):
    matchType = models.ForeignKey('matches.MatchType', on_delete=models.CASCADE, related_name='matches')
    status = models.CharField(max_length=16, choices=[('WAITING','WAITING'),('STARTING','STARTING'),('IN_PROGRESS','IN_PROGRESS'),('COMPLETED','COMPLETED'),('CANCELLED','CANCELLED')])
    gridSize = models.IntegerField()
    speed = models.CharField(max_length=16)
    currentPlayers = models.IntegerField(default=0)
    playersRequired = models.IntegerField()
    totalPot = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    winner = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, related_name='matchesWon')
    forceStartedBy = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, related_name='forcedMatches')
    startedAt = models.DateTimeField(null=True, blank=True)
    completedAt = models.DateTimeField(null=True, blank=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    isSoloMode = models.BooleanField(default=False)

    def __str__(self):
        return f"Match({self.id})"


class MatchParticipation(models.Model):
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='participants')
    player = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='matchParticipations')
    entryFeePaid = models.DecimalField(max_digits=12, decimal_places=2)
    placement = models.IntegerField(null=True, blank=True)
    wallsHit = models.IntegerField(default=0)
    botsEliminated = models.IntegerField(default=0)
    survivalTime = models.IntegerField(null=True, blank=True)
    coinReward = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    joinedAt = models.DateTimeField(auto_now_add=True)
    eliminatedAt = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('match', 'player')

    def __str__(self):
        return f"MatchParticipation({self.match_id}, {self.player_id})"


class GameState(models.Model):
    match = models.ForeignKey('matches.Match', on_delete=models.CASCADE, related_name='gameStates')
    tickNumber = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    playerPositions = models.JSONField()
    walls = models.JSONField()
    countdownWalls = models.JSONField()
    activePlayers = models.IntegerField()

    class Meta:
        ordering = ['tickNumber']

    def __str__(self):
        return f"GameState(match={self.match_id}, tick={self.tickNumber})"


class SoloRun(models.Model):
    player = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='soloRuns')
    wallsSurvived = models.IntegerField(default=0)
    wallsHit = models.IntegerField(default=0)
    coinsEarned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coinsLost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    netCoins = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    survivalTime = models.IntegerField()
    finalGridState = models.JSONField(null=True, blank=True)
    startedAt = models.DateTimeField(auto_now_add=True)
    endedAt = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"SoloRun({self.player_id}, {self.startedAt})"
