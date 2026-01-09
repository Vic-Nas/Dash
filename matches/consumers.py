import json
import asyncio
import random
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.db.models import F
from decimal import Decimal
from .models import Match, MatchParticipation
from shop.models import Transaction

# Active games {matchId: GameEngine instance}
ACTIVE_GAMES = {}

class GameEngine:
    def __init__(self, matchId, gridSize, speed, livesPerPlayer):
        self.matchId = matchId
        self.gridSize = gridSize
        self.speed = speed
        self.livesPerPlayer = livesPerPlayer
        
        # Speed to tick rate mapping (ms)
        speedMap = {'SLOW': 200, 'MEDIUM': 150, 'FAST': 100, 'EXTREME': 75}
        self.tickRate = speedMap.get(speed, 150) / 1000  # Convert to seconds
        
        self.players = {}  # {userId: {x, y, direction, alive, lives, username, playerColor}}
        self.walls = []
        self.countdownWalls = []
        self.tickNumber = 0
        self.running = False
        self.task = None
        self.wallSpawnTask = None
        
        # Player identification colors (well-spaced on color wheel)
        self.availableColors = [
            '#5b7bff',  # Blue
            '#10b981',  # Green
            '#f59e0b',  # Orange
            '#ec4899',  # Pink
            '#8b5cf6',  # Purple
            '#06b6d4',  # Cyan
            '#ef4444',  # Red
            '#84cc16',  # Lime
            '#f97316',  # Deep Orange
            '#14b8a6',  # Teal
        ]
    
    def addPlayer(self, userId, username, playerColor):
        if userId in self.players:
            return
        
        # Spawn at random position
        x = random.randint(1, self.gridSize - 2)
        y = random.randint(1, self.gridSize - 2)
        
        self.players[userId] = {
            'username': username,
            'x': x,
            'y': y,
            'direction': random.choice(['UP', 'DOWN', 'LEFT', 'RIGHT']),
            'alive': True,
            'lives': self.livesPerPlayer,
            'playerColor': playerColor,
        }
    
    def updateDirection(self, userId, direction):
        if userId in self.players and self.players[userId]['alive']:
            self.players[userId]['direction'] = direction
    
    def tick(self):
        self.tickNumber += 1
        
        # Move all alive players
        for userId, player in self.players.items():
            if not player['alive']:
                continue
            
            newX, newY = player['x'], player['y']
            
            if player['direction'] == 'UP':
                newY -= 1
            elif player['direction'] == 'DOWN':
                newY += 1
            elif player['direction'] == 'LEFT':
                newX -= 1
            elif player['direction'] == 'RIGHT':
                newX += 1
            
            # Check edge collision - treat as wall hit
            if newX < 0 or newX >= self.gridSize or newY < 0 or newY >= self.gridSize:
                self.handleCollision(userId)
                continue
            
            # Check wall collision
            if any(w['x'] == newX and w['y'] == newY for w in self.walls):
                self.handleCollision(userId)
                continue
            
            # Check player collision (from side/back = other dies, head-on = both die)
            for otherId, other in self.players.items():
                if otherId != userId and other['alive']:
                    if other['x'] == newX and other['y'] == newY:
                        # Both players collide head-on
                        self.handleCollision(userId)
                        self.handleCollision(otherId)
                        continue
            
            # Valid move
            player['x'] = newX
            player['y'] = newY
    
    def handleCollision(self, userId):
        player = self.players[userId]
        
        if self.livesPerPlayer == 0:
            # Instant death mode
            player['alive'] = False
        else:
            # Lives mode
            player['lives'] -= 1
            if player['lives'] <= 0:
                player['alive'] = False
    
    def spawnWall(self):
        attempts = 0
        while attempts < 100:
            x = random.randint(0, self.gridSize - 1)
            y = random.randint(0, self.gridSize - 1)
            
            # Check if position is occupied
            occupied = any(w['x'] == x and w['y'] == y for w in self.walls)
            occupied = occupied or any(w['x'] == x and w['y'] == y for w in self.countdownWalls)
            occupied = occupied or any(p['x'] == x and p['y'] == y and p['alive'] for p in self.players.values())
            
            if not occupied:
                self.countdownWalls.append({'x': x, 'y': y, 'secondsLeft': 3})
                break
            
            attempts += 1
    
    def updateCountdownWalls(self):
        toRemove = []
        for wall in self.countdownWalls:
            wall['secondsLeft'] -= 1
            if wall['secondsLeft'] <= 0:
                self.walls.append({'x': wall['x'], 'y': wall['y']})
                toRemove.append(wall)
        
        for wall in toRemove:
            self.countdownWalls.remove(wall)
    
    def getState(self):
        return {
            'tick': self.tickNumber,
            'players': self.players,
            'walls': self.walls,
            'countdownWalls': self.countdownWalls,
            'aliveCount': sum(1 for p in self.players.values() if p['alive'])
        }
    
    def checkGameOver(self):
        alive = [uid for uid, p in self.players.items() if p['alive']]
        if len(alive) <= 1:
            return alive[0] if alive else None
        return None
    
    async def start(self, broadcastCallback):
        self.running = True
        
        # Main game loop
        async def gameLoop():
            while self.running:
                self.tick()
                await broadcastCallback(self.getState())
                
                winnerId = self.checkGameOver()
                if winnerId is not None:
                    await self.endGame(winnerId, broadcastCallback)
                    break
                
                await asyncio.sleep(self.tickRate)
        
        # Wall countdown loop
        async def countdownLoop():
            while self.running:
                await asyncio.sleep(1)
                self.updateCountdownWalls()
        
        # Wall spawn loop
        async def spawnLoop():
            while self.running:
                await asyncio.sleep(3)
                self.spawnWall()
        
        self.task = asyncio.create_task(gameLoop())
        self.wallSpawnTask = asyncio.create_task(spawnLoop())
        asyncio.create_task(countdownLoop())
    
    async def endGame(self, winnerId, broadcastCallback):
        self.running = False
        
        # Determine if it's a tie
        alivePlayers = [uid for uid, p in self.players.items() if p['alive']]
        isTie = len(alivePlayers) == 0
        
        await broadcastCallback({
            'type': 'gameOver',
            'winnerId': winnerId if not isTie else None,
            'winnerUsername': self.players[winnerId]['username'] if winnerId and not isTie else None,
            'isTie': isTie,
            'alivePlayers': alivePlayers
        })
    
    def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
        if self.wallSpawnTask:
            self.wallSpawnTask.cancel()


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.matchId = self.scope['url_route']['kwargs']['matchId']
        self.roomGroupName = f'match_{self.matchId}'
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.roomGroupName,
            self.channel_name
        )
        
        await self.accept()
        
        # Check if player is in this match
        participation = await self.getParticipation()
        if not participation:
            await self.close()
            return
        
        # Get player's assigned color
        playerColor = await self.getPlayerColor()
        
        # Get or create game engine
        if self.matchId not in ACTIVE_GAMES:
            match = await self.getMatch()
            engine = GameEngine(
                self.matchId,
                match.gridSize,
                match.speed,
                match.matchType.livesPerPlayer
            )
            ACTIVE_GAMES[self.matchId] = engine
        
        engine = ACTIVE_GAMES[self.matchId]
        
        # Add player with their color
        engine.addPlayer(
            self.user.id,
            self.user.username,
            playerColor
        )
        
        # Send player their assigned color
        await self.send(text_data=json.dumps({
            'type': 'playerColor',
            'playerColor': playerColor
        }))
        
        # If match should start, start it
        match = await self.getMatch()
        if match.status == 'STARTING' and not engine.running:
            await self.startMatch()
            await engine.start(self.broadcastState)
    
    async def disconnect(self, closeCode):
        await self.channel_layer.group_discard(
            self.roomGroupName,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        
        if action == 'changeDirection':
            direction = data.get('direction')
            if direction in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
                engine = ACTIVE_GAMES.get(self.matchId)
                if engine:
                    engine.updateDirection(self.user.id, direction)
    
    async def gameState(self, event):
        await self.send(text_data=json.dumps(event['state']))
    
    async def broadcastState(self, state):
        # Handle game over
        if state.get('type') == 'gameOver':
            await self.handleGameOver(state)
        
        await self.channel_layer.group_send(
            self.roomGroupName,
            {
                'type': 'gameState',
                'state': state
            }
        )
    
    async def handleGameOver(self, state):
        """Handle game over - award pot to winner(s)"""
        match = await self.getMatch()
        
        isTie = state.get('isTie', False)
        winnerId = state.get('winnerId')
        
        if isTie:
            await self.splitPot(match)
        elif winnerId:
            await self.awardPot(match, winnerId)
        
        await self.completeMatch(match, winnerId)
    
    @database_sync_to_async
    def getPlayerColor(self):
        """Get player's assigned color based on join order"""
        match = Match.objects.get(id=self.matchId)
        allParticipants = list(match.participants.order_by('joinedAt').values_list('player_id', flat=True))
        playerIndex = allParticipants.index(self.user.id)
        
        colors = [
            '#5b7bff',  # Blue
            '#10b981',  # Green
            '#f59e0b',  # Orange
            '#ec4899',  # Pink
            '#8b5cf6',  # Purple
            '#06b6d4',  # Cyan
            '#ef4444',  # Red
            '#84cc16',  # Lime
            '#f97316',  # Deep Orange
            '#14b8a6',  # Teal
        ]
        
        return colors[playerIndex % len(colors)]
    
    @database_sync_to_async
    def splitPot(self, match):
        """Split pot equally among all participants"""
        from django.db import transaction as dbTransaction
        
        with dbTransaction.atomic():
            match = Match.objects.select_for_update().get(id=match.id)
            participants = list(match.participants.select_related('player__profile').all())
            
            if not participants:
                return
            
            share = match.totalPot / len(participants)
            
            for participation in participants:
                profile = participation.player.profile
                profile = type(profile).objects.select_for_update().get(pk=profile.pk)
                
                balanceBefore = profile.coins
                profile.coins = F('coins') + share
                profile.save(update_fields=['coins'])
                profile.refresh_from_db()
                
                participation.coinReward = share
                participation.placement = 1
                participation.save(update_fields=['coinReward', 'placement'])
                
                Transaction.objects.create(
                    user=participation.player,
                    amount=share,
                    transactionType='MATCH_WIN',
                    relatedMatch=match,
                    description=f'Tie - Split pot: {match.matchType.name}',
                    balanceBefore=balanceBefore,
                    balanceAfter=profile.coins
                )
    
    @database_sync_to_async
    def awardPot(self, match, winnerId):
        """Award full pot to winner"""
        from django.db import transaction as dbTransaction
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        with dbTransaction.atomic():
            match = Match.objects.select_for_update().get(id=match.id)
            winner = User.objects.get(id=winnerId)
            
            profile = winner.profile
            profile = type(profile).objects.select_for_update().get(pk=profile.pk)
            
            balanceBefore = profile.coins
            profile.coins = F('coins') + match.totalPot
            profile.totalWins = F('totalWins') + 1
            profile.save(update_fields=['coins', 'totalWins'])
            profile.refresh_from_db()
            
            participation = MatchParticipation.objects.get(match=match, player=winner)
            participation.coinReward = match.totalPot
            participation.placement = 1
            participation.save(update_fields=['coinReward', 'placement'])
            
            Transaction.objects.create(
                user=winner,
                amount=match.totalPot,
                transactionType='MATCH_WIN',
                relatedMatch=match,
                description=f'Won match: {match.matchType.name}',
                balanceBefore=balanceBefore,
                balanceAfter=profile.coins
            )
    
    @database_sync_to_async
    def completeMatch(self, match, winnerId):
        """Mark match as completed"""
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        match.status = 'COMPLETED'
        match.completedAt = timezone.now()
        if winnerId:
            match.winner = User.objects.get(id=winnerId)
        match.save(update_fields=['status', 'completedAt', 'winner'])
        
        for participation in match.participants.select_related('player__profile').all():
            profile = participation.player.profile
            profile.totalMatches = F('totalMatches') + 1
            profile.save(update_fields=['totalMatches'])
    
    @database_sync_to_async
    def getParticipation(self):
        try:
            return MatchParticipation.objects.get(
                match_id=self.matchId,
                player=self.user
            )
        except MatchParticipation.DoesNotExist:
            return None
    
    @database_sync_to_async
    def getMatch(self):
        return Match.objects.select_related('matchType').get(id=self.matchId)
    
    @database_sync_to_async
    def startMatch(self):
        match = Match.objects.get(id=self.matchId)
        match.status = 'IN_PROGRESS'
        match.startedAt = timezone.now()
        match.save()