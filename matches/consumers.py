import json
import asyncio
import random
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.utils import timezone
from django.db.models import F
from decimal import Decimal
from .models import Match, MatchParticipation
from shop.models import Transaction

# Active games {matchId: GameEngine instance}
ACTIVE_GAMES = {}
# Active countdowns {matchId: asyncio.Task}
ACTIVE_COUNTDOWNS = {}

class GameEngine:
    def __init__(self, matchId, gridSize, speed, wallSpawnInterval):
        self.matchId = matchId
        self.gridSize = gridSize
        self.speed = speed
        self.wallSpawnInterval = wallSpawnInterval
        
        # Speed to tick rate mapping (ms)
        speedMap = {'SLOW': 200, 'MEDIUM': 150, 'FAST': 100, 'EXTREME': 75}
        self.tickRate = speedMap.get(speed, 150) / 1000
        
        self.players = {}
        self.walls = []
        self.countdownWalls = []
        self.tickNumber = 0
        self.running = False
        self.task = None
        self.wallSpawnTask = None
        
        self.availableColors = [
            '#5b7bff', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6',
            '#06b6d4', '#ef4444', '#84cc16', '#f97316', '#14b8a6',
        ]
    
    def addPlayer(self, userId, username, playerColor):
        if userId in self.players:
            return
        
        x = random.randint(1, self.gridSize - 2)
        y = random.randint(1, self.gridSize - 2)
        
        self.players[userId] = {
            'username': username,
            'x': x,
            'y': y,
            'direction': random.choice(['UP', 'DOWN', 'LEFT', 'RIGHT']),
            'alive': True,
            'playerColor': playerColor,
            'score': 0,  # Points gained from walls spawning
            'hits': 0,   # Track hits separately
        }
    
    def updateDirection(self, userId, direction):
        if userId in self.players and self.players[userId]['alive']:
            self.players[userId]['direction'] = direction
    
    def tick(self):
        self.tickNumber += 1
        
        newPositions = {}
        
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
            
            newPositions[userId] = (newX, newY)
        
        for userId, (newX, newY) in newPositions.items():
            player = self.players[userId]
            
            # Check wall/edge hit
            if newX < 0 or newX >= self.gridSize or newY < 0 or newY >= self.gridSize:
                self.handleWallHit(userId)
                continue
            
            if any(w['x'] == newX and w['y'] == newY for w in self.walls):
                self.handleWallHit(userId)
                continue
            
            collision = False
            for otherId, otherPlayer in self.players.items():
                if otherId != userId and otherPlayer['alive']:
                    if otherId in newPositions:
                        otherNewX, otherNewY = newPositions[otherId]
                        # Head-on collision
                        if newX == otherNewX and newY == otherNewY:
                            self.handleWallHit(userId)
                            self.handleWallHit(otherId)
                            collision = True
                            break
                    
                    # Hit another player from side/back
                    if newX == otherPlayer['x'] and newY == otherPlayer['y']:
                        self.handlePlayerCollision(attackerId=userId, victimId=otherId)
                        collision = True
                        break
            
            if collision:
                continue
            
            player['x'] = newX
            player['y'] = newY
    
    def handleWallHit(self, userId):
        """Player hit wall or edge - increment hits counter"""
        player = self.players[userId]
        player['hits'] += 1  # Track hits
        
        # Eliminate after 50 hits
        if player['hits'] >= 50:
            player['alive'] = False
    
    def handlePlayerCollision(self, attackerId, victimId):
        """Attacker eliminates victim and gains their score"""
        attacker = self.players[attackerId]
        victim = self.players[victimId]
        
        victim['alive'] = False
        
        # Gain victim's positive score (not their hits)
        pointsGained = max(0, victim['score'])
        attacker['score'] += pointsGained
    
    def spawnWall(self):
        attempts = 0
        while attempts < 100:
            x = random.randint(0, self.gridSize - 1)
            y = random.randint(0, self.gridSize - 1)
            
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
                
                # All alive players gain +1 point
                for player in self.players.values():
                    if player['alive']:
                        player['score'] += 1
                
                toRemove.append(wall)
        
        for wall in toRemove:
            self.countdownWalls.remove(wall)
    
    def getState(self):
        return {
            'tick': self.tickNumber,
            'players': {str(uid): p for uid, p in self.players.items()},
            'walls': self.walls,
            'countdownWalls': self.countdownWalls,
            'aliveCount': sum(1 for p in self.players.values() if p['alive'])
        }
    
    def checkGameOver(self):
        alive = [uid for uid, p in self.players.items() if p['alive']]
        if len(alive) <= 1:
            return alive[0] if alive else None
        return None
    
    async def start(self, roomGroupName, handleGameOverCallback):
        self.running = True
        channel_layer = get_channel_layer()
        
        async def gameLoop():
            while self.running:
                self.tick()
                state = self.getState()
                
                # Broadcast state
                await channel_layer.group_send(
                    roomGroupName,
                    {
                        'type': 'gameState',
                        'state': state
                    }
                )
                
                winnerId = self.checkGameOver()
                if winnerId is not None:
                    await self.endGame(winnerId, roomGroupName, handleGameOverCallback)
                    break
                
                await asyncio.sleep(self.tickRate)
        
        async def countdownLoop():
            while self.running:
                await asyncio.sleep(1)
                self.updateCountdownWalls()
        
        async def spawnLoop():
            while self.running:
                await asyncio.sleep(self.wallSpawnInterval)
                self.spawnWall()
        
        self.task = asyncio.create_task(gameLoop())
        self.wallSpawnTask = asyncio.create_task(spawnLoop())
        asyncio.create_task(countdownLoop())
    
    async def endGame(self, winnerId, roomGroupName, handleGameOverCallback):
        self.running = False
        channel_layer = get_channel_layer()
        
        alivePlayers = [uid for uid, p in self.players.items() if p['alive']]
        isTie = len(alivePlayers) == 0
        
        gameOverState = {
            'type': 'gameOver',
            'winnerId': winnerId if not isTie else None,
            'winnerUsername': self.players[winnerId]['username'] if winnerId and not isTie else None,
            'isTie': isTie,
            'alivePlayers': alivePlayers,
            'finalScores': {str(uid): p['score'] for uid, p in self.players.items()},
            'finalHits': {str(uid): p['hits'] for uid, p in self.players.items()}
        }
        
        # Handle rewards
        await handleGameOverCallback(gameOverState)
        
        # Broadcast game over
        await channel_layer.group_send(
            roomGroupName,
            {
                'type': 'gameState',
                'state': gameOverState
            }
        )
    
    def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
        if self.wallSpawnTask:
            self.wallSpawnTask.cancel()


async def startMatchCountdown(matchId, roomGroupName, engine):
    """Standalone countdown function that doesn't depend on consumer instance"""
    channel_layer = get_channel_layer()
    
    try:
        print(f"[Match {matchId}] Starting countdown")
        
        # Broadcast countdown
        for i in range(10, 0, -1):
            print(f"[Match {matchId}] Countdown: {i}")
            await channel_layer.group_send(
                roomGroupName,
                {
                    'type': 'gameState',
                    'state': {
                        'type': 'countdown',
                        'seconds': i
                    }
                }
            )
            await asyncio.sleep(1)
        
        # Update match status to IN_PROGRESS
        print(f"[Match {matchId}] Countdown complete, starting match")
        from django.contrib.auth import get_user_model
        
        @database_sync_to_async
        def setMatchInProgress():
            match = Match.objects.get(id=matchId)
            match.status = 'IN_PROGRESS'
            match.startedAt = timezone.now()
            match.save()
        
        @database_sync_to_async
        def handleGameOver(state):
            # This will be called when game ends
            match = Match.objects.select_related('matchType').get(id=matchId)
            
            isTie = state.get('isTie', False)
            winnerId = state.get('winnerId')
            
            if isTie:
                splitPot(match)
            elif winnerId:
                awardPot(match, winnerId)
            
            completeMatch(match, winnerId)
        
        def splitPot(match):
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
        
        def awardPot(match, winnerId):
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
        
        def completeMatch(match, winnerId):
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
        
        await setMatchInProgress()
        print(f"[Match {matchId}] Match status updated, starting engine")
        
        await engine.start(roomGroupName, handleGameOver)
        print(f"[Match {matchId}] Engine started successfully")
        
    except Exception as e:
        print(f"[Match {matchId}] ERROR in countdown: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if matchId in ACTIVE_COUNTDOWNS:
            del ACTIVE_COUNTDOWNS[matchId]


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.matchId = self.scope['url_route']['kwargs']['matchId']
        self.roomGroupName = f'match_{self.matchId}'
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        await self.channel_layer.group_add(
            self.roomGroupName,
            self.channel_name
        )
        
        await self.accept()
        
        participation = await self.getParticipation()
        if not participation:
            await self.close()
            return
        
        playerColor = await self.getPlayerColor()
        
        if self.matchId not in ACTIVE_GAMES:
            match = await self.getMatch()
            engine = GameEngine(
                self.matchId,
                match.gridSize,
                match.speed,
                match.matchType.wallSpawnInterval
            )
            ACTIVE_GAMES[self.matchId] = engine
        
        engine = ACTIVE_GAMES[self.matchId]
        
        engine.addPlayer(
            self.user.id,
            self.user.username,
            playerColor
        )
        
        await self.send(text_data=json.dumps({
            'type': 'playerColor',
            'playerColor': playerColor
        }))
        
        match = await self.getMatch()
        
        # If match is STARTING and countdown hasn't started yet, start it ONCE
        if match.status == 'STARTING' and not engine.running:
            if self.matchId not in ACTIVE_COUNTDOWNS:
                ACTIVE_COUNTDOWNS[self.matchId] = asyncio.create_task(
                    startMatchCountdown(self.matchId, self.roomGroupName, engine)
                )
        
        # If already IN_PROGRESS but engine not running (shouldn't happen but just in case)
        elif match.status == 'IN_PROGRESS' and not engine.running:
            # This shouldn't happen in normal flow, but handle it
            pass
    
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
    
    @database_sync_to_async
    def getPlayerColor(self):
        match = Match.objects.get(id=self.matchId)
        allParticipants = list(match.participants.order_by('joinedAt').values_list('player_id', flat=True))
        playerIndex = allParticipants.index(self.user.id)
        
        colors = [
            '#5b7bff', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6',
            '#06b6d4', '#ef4444', '#84cc16', '#f97316', '#14b8a6',
        ]
        
        return colors[playerIndex % len(colors)]
    
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