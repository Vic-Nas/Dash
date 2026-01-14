
from django.db import models
from django.contrib.auth import get_user_model

class ReplayView(models.Model):
    user = models.ForeignKey('accounts.Profile', on_delete=models.CASCADE, related_name='replayViews')
    replay_type = models.CharField(max_length=16)
    replay_id = models.IntegerField()
    paid = models.BooleanField(default=False)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'replay_type', 'replay_id')


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
    hasBot = models.BooleanField(default=True, help_text="Automatically add 1 bot to the lobby")
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
    player = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='matchParticipations', null=True, blank=True)
    username = models.CharField(max_length=100, null=True, blank=True, help_text="Username for bot players")
    entryFeePaid = models.DecimalField(max_digits=12, decimal_places=2)
    placement = models.IntegerField(null=True, blank=True)
    wallsHit = models.IntegerField(default=0)
    botsEliminated = models.IntegerField(default=0)
    survivalTime = models.IntegerField(null=True, blank=True)
    coinReward = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    isBot = models.BooleanField(default=False, help_text="Is this a bot player")
    joinedAt = models.DateTimeField(auto_now_add=True)
    eliminatedAt = models.DateTimeField(null=True, blank=True)
    replayData = models.JSONField(null=True, blank=True)
    isPublic = models.BooleanField(default=True)

    class Meta:
        unique_together = ('match', 'player')

    def __str__(self):
        player_id = f"Bot_{self.username}" if self.isBot else self.player_id
        return f"MatchParticipation({self.match_id}, {player_id})"


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
    replayData = models.JSONField(null=True, blank=True)
    isPublic = models.BooleanField(default=True)
    startedAt = models.DateTimeField(auto_now_add=True)
    endedAt = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"SoloRun({self.player_id}, {self.startedAt})"


class ProgressiveRun(models.Model):
    player = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='progressiveRuns')
    level = models.IntegerField()
    botsEliminated = models.IntegerField(default=0)
    won = models.BooleanField(default=False)
    survivalTime = models.IntegerField()
    coinsSpent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coinsEarned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    finalGridState = models.JSONField(null=True, blank=True)
    replayData = models.JSONField(null=True, blank=True)
    isPublic = models.BooleanField(default=True)
    startedAt = models.DateTimeField(auto_now_add=True)
    endedAt = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"ProgressiveRun({self.player_id}, Level {self.level})"