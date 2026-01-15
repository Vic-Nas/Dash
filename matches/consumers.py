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
        self.replayFrames = []  # ADD THIS
    
    def addPlayer(self, userId, username, playerColor, isBot=False):
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
            'score': 0,
            'hits': 0,
            'isBot': isBot,
            'botDirectionChangeCounter': 0,  # For bot AI
            'botNextDirectionChangeAt': random.randint(5, 10),  # Bot changes direction every 5-10 ticks
        }
    
    def removePlayer(self, userId):
        """Remove a player from the game"""
        if userId in self.players:
            del self.players[userId]
    
    def updateBotAI(self, userId, player):
        """Update bot player AI - REACTIVE wall avoidance every tick, not just periodic"""
        from shop.models import SystemSettings
        
        x, y = player['x'], player['y']
        currentDir = player.get('direction', 'UP')
        
        # FIRST: Check if current direction is unsafe - if so, IMMEDIATELY change
        nextX, nextY = x, y
        if currentDir == 'UP':
            nextY -= 1
        elif currentDir == 'DOWN':
            nextY += 1
        elif currentDir == 'LEFT':
            nextX -= 1
        elif currentDir == 'RIGHT':
            nextX += 1
        
        # Check if next move would be bad (boundary or wall)
        isCurrentDirUnsafe = (
            nextX < 0 or nextX >= self.gridSize or 
            nextY < 0 or nextY >= self.gridSize or
            any(w['x'] == nextX and w['y'] == nextY for w in self.walls) or
            any(w['x'] == nextX and w['y'] == nextY for w in self.countdownWalls)
        )
        
        # Periodically pick a new direction (keep it shorter - 4-8 ticks)
        player['botDirectionChangeCounter'] = player.get('botDirectionChangeCounter', 0) + 1
        
        if player['botDirectionChangeCounter'] >= player.get('botNextDirectionChangeAt', 5):
            player['botDirectionChangeCounter'] = 0
            player['botNextDirectionChangeAt'] = random.randint(4, 8)
            isCurrentDirUnsafe = True  # Force direction change
        
        # If current direction is unsafe OR timer expired, pick a new safe direction
        if isCurrentDirUnsafe:
            directions = ['UP', 'DOWN', 'LEFT', 'RIGHT']
            
            # Find all safe directions
            safeDirections = []
            for direction in directions:
                testX, testY = x, y
                if direction == 'UP':
                    testY -= 1
                elif direction == 'DOWN':
                    testY += 1
                elif direction == 'LEFT':
                    testX -= 1
                elif direction == 'RIGHT':
                    testX += 1
                
                # Check boundaries (strict - avoid edges)
                if testX < 1 or testX >= self.gridSize - 1 or testY < 1 or testY >= self.gridSize - 1:
                    continue
                
                # Check wall collision
                if any(w['x'] == testX and w['y'] == testY for w in self.walls):
                    continue
                
                # Check countdown wall collision
                if any(w['x'] == testX and w['y'] == testY for w in self.countdownWalls):
                    continue
                
                safeDirections.append(direction)
            
            # Pick a safe direction
            if safeDirections:
                player['direction'] = random.choice(safeDirections)
            else:
                # If trapped, pick any direction
                player['direction'] = random.choice(directions)
        
        # Very rarely move random (1% chance)
        if random.random() < 0.01:
            player['direction'] = random.choice(['UP', 'DOWN', 'LEFT', 'RIGHT'])
    
    def updateDirection(self, userId, direction):
        if userId in self.players and self.players[userId]['alive']:
            # Don't allow direction updates for bots during their AI decision
            if not self.players[userId].get('isBot', False):
                self.players[userId]['direction'] = direction
    
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
    
    def tick(self):
        try:
            self.tickNumber += 1
            
            # STEP 1: Update bot AI
            try:
                for userId in list(self.players.keys()):  # Use list() to avoid dict mutation issues
                    if userId not in self.players:
                        continue
                    player = self.players[userId]
                    if player['alive'] and player.get('isBot', False):
                        self.updateBotAI(userId, player)
            except Exception as e:
                print(f"[Match {self.matchId}] Error updating bot AI: {e}")
            
            # STEP 2: Calculate new positions for all players
            newPositions = {}
            try:
                for userId in list(self.players.keys()):
                    if userId not in self.players:
                        continue
                    player = self.players[userId]
                    if not player['alive']:
                        continue
                    
                    x, y = player['x'], player['y']
                    direction = player.get('direction', 'UP')
                    
                    if direction == 'UP':
                        y -= 1
                    elif direction == 'DOWN':
                        y += 1
                    elif direction == 'LEFT':
                        x -= 1
                    elif direction == 'RIGHT':
                        x += 1
                    
                    newPositions[userId] = (x, y)
            except Exception as e:
                print(f"[Match {self.matchId}] Error calculating positions: {e}")
                return
            
            # STEP 3: Process collisions and position updates
            processedHeadOns = set()
            try:
                for userId in list(newPositions.keys()):
                    if userId not in self.players or userId not in newPositions:
                        continue
                    
                    player = self.players[userId]
                    newX, newY = newPositions[userId]
                    
                    # Check boundaries
                    if newX < 0 or newX >= self.gridSize or newY < 0 or newY >= self.gridSize:
                        self.handleWallHit(userId)
                        continue
                    
                    # Check wall collision
                    wallHit = False
                    for wall in self.walls:
                        if wall['x'] == newX and wall['y'] == newY:
                            wallHit = True
                            break
                    
                    if wallHit:
                        self.handleWallHit(userId)
                        continue
                    
                    # Check player collisions
                    collision = False
                    
                    # Check head-on collisions (both moving to same spot)
                    for otherId in list(self.players.keys()):
                        if otherId not in self.players or otherId == userId:
                            continue
                        if not self.players[otherId]['alive']:
                            continue
                        if otherId not in newPositions:
                            continue
                        
                        otherX, otherY = newPositions[otherId]
                        if newX == otherX and newY == otherY:
                            collisionKey = tuple(sorted([userId, otherId]))
                            if collisionKey not in processedHeadOns:
                                # Head-on collision: treat like wall hit (both take damage)
                                self.handleWallHit(userId)
                                self.handleWallHit(otherId)
                                processedHeadOns.add(collisionKey)
                            collision = True
                            break
                    if collision:
                        continue
                    
                    # Check side/back collisions (moving into current position)
                    for otherId in list(self.players.keys()):
                        if otherId not in self.players or otherId == userId:
                            continue
                        if not self.players[otherId]['alive']:
                            continue
                        
                        otherPlayer = self.players[otherId]
                        if newX == otherPlayer['x'] and newY == otherPlayer['y']:
                            self.handlePlayerCollision(attackerId=userId, victimId=otherId)
                            collision = True
                            break
                    
                    if collision:
                        continue
                    
                    # No collision - update position
                    if userId in self.players:
                        self.players[userId]['x'] = newX
                        self.players[userId]['y'] = newY
            
            except Exception as e:
                print(f"[Match {self.matchId}] Error processing collisions: {e}")
                import traceback
                traceback.print_exc()
                return
            
            # STEP 4: Record frame
            try:
                self.recordFrame()
            except Exception as e:
                print(f"[Match {self.matchId}] Error recording frame: {e}")
        
        except Exception as e:
            print(f"[Match {self.matchId}] Critical error in tick: {e}")
            import traceback
            traceback.print_exc()
    
    def recordFrame(self):
        """Record current game state for replay"""
        try:
            frame = {
                'gridSize': self.gridSize,
                'players': {},
                'walls': [],
                'countdownWalls': [],
            }
            
            # Safely copy walls
            try:
                for w in self.walls:
                    frame['walls'].append({'x': w['x'], 'y': w['y']})
            except Exception as e:
                print(f"[Match {self.matchId}] Error recording walls: {e}")
            
            # Safely copy countdown walls
            try:
                for w in self.countdownWalls:
                    frame['countdownWalls'].append({'x': w['x'], 'y': w['y'], 'secondsLeft': w['secondsLeft']})
            except Exception as e:
                print(f"[Match {self.matchId}] Error recording countdown walls: {e}")
            
            # Safely copy player data
            for userId in list(self.players.keys()):
                try:
                    if userId not in self.players:
                        continue
                    player = self.players[userId]
                    frame['players'][str(userId)] = {
                        'x': player.get('x', 0),
                        'y': player.get('y', 0),
                        'direction': player.get('direction', 'UP'),
                        'alive': player.get('alive', False),
                        'score': player.get('score', 0),
                        'hits': player.get('hits', 0),
                        'username': player.get('username', 'Unknown'),
                        'playerColor': player.get('playerColor', '#ffffff')
                    }
                except Exception as e:
                    print(f"[Match {self.matchId}] Error recording player {userId}: {e}")
            
            self.replayFrames.append(frame)
        except Exception as e:
            print(f"[Match {self.matchId}] Critical error in recordFrame: {e}")
    
    def handleWallHit(self, userId):
        """Handle player hitting a wall or boundary"""
        if userId not in self.players:
            return
        
        player = self.players[userId]
        if not player['alive']:
            # Already dead, don't process again
            return
        
        player['hits'] += 1
        
        # Eliminate after 50 hits
        if player['hits'] >= 50:
            player['alive'] = False
    
    def handlePlayerCollision(self, attackerId, victimId):
        """Attacker eliminates victim and gains their score"""
        if attackerId not in self.players or victimId not in self.players:
            return
        
        attacker = self.players[attackerId]
        victim = self.players[victimId]
        
        # Don't process if victim already dead
        if not victim['alive']:
            return
        
        # Gain victim's positive score (not their hits)
        pointsGained = max(0, victim['score'])
        attacker['score'] += pointsGained
        
        # Victim loses all their score on elimination
        victim['score'] = 0
        victim['alive'] = False
    
    def getState(self):
        return {
            'tick': self.tickNumber,
            'gridSize': self.gridSize,
            'players': {str(uid): p for uid, p in self.players.items()},
            'walls': self.walls,
            'countdownWalls': self.countdownWalls,
            'aliveCount': sum(1 for p in self.players.values() if p['alive'])
        }
    
    def checkGameOver(self):
        alive = [uid for uid, p in self.players.items() if p['alive']]
        # Game only ends when:
        # 1) 1 player remains alive AND there were at least 2 players to begin with, OR
        # 2) 0 players remain (tie)
        if len(alive) <= 1:
            # Only end if we had multiple players in the match
            totalPlayers = len(self.players)
            if totalPlayers >= 2:
                return alive[0] if alive else None
        return None
    
    async def start(self, roomGroupName, handleGameOverCallback):
        self.running = True
        channel_layer = get_channel_layer()
        
        async def gameLoop():
            last_log_tick = 0
            while self.running:
                try:
                    self.tick()
                    
                    # Log every 100 ticks to detect hangs
                    if self.tickNumber % 100 == 0 and self.tickNumber != last_log_tick:
                        last_log_tick = self.tickNumber
                        print(f"[Match {self.matchId}] Tick {self.tickNumber}, Players: {sum(1 for p in self.players.values() if p['alive'])} alive")
                    
                    state = self.getState()
                    
                    # Broadcast state
                    try:
                        await channel_layer.group_send(
                            roomGroupName,
                            {
                                'type': 'gameState',
                                'state': state
                            }
                        )
                    except Exception as e:
                        print(f"[Match {self.matchId}] Failed to broadcast state: {e}")
                    
                    winnerId = self.checkGameOver()
                    if winnerId is not None:
                        await self.endGame(winnerId, roomGroupName, handleGameOverCallback)
                        break
                    
                    # Also check if game is over due to tie (everyone dead)
                    aliveCount = sum(1 for p in self.players.values() if p['alive'])
                    if aliveCount == 0:
                        await self.endGame(None, roomGroupName, handleGameOverCallback)
                        break
                    
                    await asyncio.sleep(self.tickRate)
                except Exception as e:
                    print(f"[GameEngine {self.matchId}] Error in gameLoop: {e}")
                    self.running = False
                    break
        
        async def countdownLoop():
            while self.running:
                try:
                    await asyncio.sleep(1)
                    self.updateCountdownWalls()
                except Exception as e:
                    print(f"[GameEngine {self.matchId}] Error in countdownLoop: {e}")
        
        async def spawnLoop():
            # FIX: Only spawn walls if wallSpawnInterval > 0
            if self.wallSpawnInterval <= 0:
                return
            
            while self.running:
                try:
                    await asyncio.sleep(self.wallSpawnInterval)
                    self.spawnWall()
                except Exception as e:
                    print(f"[GameEngine {self.matchId}] Error in spawnLoop: {e}")
        
        self.task = asyncio.create_task(gameLoop())
        self.wallSpawnTask = asyncio.create_task(spawnLoop())
        asyncio.create_task(countdownLoop())
    
    async def endGame(self, winnerId, roomGroupName, handleGameOverCallback):
        self.running = False
        channel_layer = get_channel_layer()
        try:
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
            # Build replay data
            replayData = {
                'frames': self.replayFrames,
                'frameDuration': int(self.tickRate * 1000),  # Convert to ms
                'mode': 'multiplayer'
            }
            # Pass replay data to callback
            gameOverState['replayData'] = replayData
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
        except Exception as e:
            import traceback
            print(f"[GameEngine {self.matchId}] Error in endGame: {e}")
            print(traceback.format_exc())
    
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
        print(f"[Match {matchId}] Starting 10-second countdown")
        
        # Broadcast countdown - 10 seconds down to 1
        for i in range(10, 0, -1):
            try:
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
            except Exception as e:
                print(f"[Match {matchId}] Failed to broadcast countdown {i}: {e}")
            
            await asyncio.sleep(1)
        
        print(f"[Match {matchId}] Countdown complete (10s elapsed), starting match engine")
        
        # Update match status to IN_PROGRESS
        from django.contrib.auth import get_user_model
        
        @database_sync_to_async
        def setMatchInProgress():
            try:
                match = Match.objects.get(id=matchId)
                match.status = 'IN_PROGRESS'
                match.startedAt = timezone.now()
                match.save()
                print(f"[Match {matchId}] Match status updated to IN_PROGRESS")
            except Exception as e:
                print(f"[Match {matchId}] Failed to update match status: {e}")
                raise
        
        async def handleGameOver(state):
            """Handle game over - process rewards and complete match"""
            try:
                print(f"[Match {matchId}] handleGameOver called with state: isTie={state.get('isTie')}, winnerId={state.get('winnerId')}")
                
                # Process in sync context
                await database_sync_to_async(lambda: handle_game_over_sync(state))()
                
                print(f"[Match {matchId}] handleGameOver completed successfully")
            except Exception as e:
                print(f"[Match {matchId}] ERROR in handleGameOver: {e}")
                import traceback
                traceback.print_exc()
        
        def handle_game_over_sync(state):
            """Synchronous game over handler - runs in thread pool"""
            from django.db import transaction as dbTransaction
            
            try:
                match = Match.objects.select_related('matchType').get(id=matchId)
                
                isTie = state.get('isTie', False)
                winnerId = state.get('winnerId')
                replayData = state.get('replayData')
                
                print(f"[Match {matchId}] Processing game over: isTie={isTie}, winnerId={winnerId}")
                
                with dbTransaction.atomic():
                    if isTie:
                        splitPot_sync(match, replayData)
                    elif winnerId:
                        awardPot_sync(match, winnerId, replayData)
                    
                    completeMatch_sync(match, winnerId)
                    
                print(f"[Match {matchId}] Game over processing completed")
            except Exception as e:
                print(f"[Match {matchId}] ERROR in handle_game_over_sync: {e}")
                import traceback
                traceback.print_exc()
                raise
        
        def splitPot_sync(match, replayData=None):
            from django.db import transaction as dbTransaction
            import json
            
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
                    if replayData:
                        participation.replayData = json.dumps(replayData) if not isinstance(replayData, str) else replayData
                    participation.save(update_fields=['coinReward', 'placement', 'replayData'])
                    
                    Transaction.objects.create(
                        user=participation.player,
                        amount=share,
                        transactionType='MATCH_WIN',
                        relatedMatch=match,
                        description=f'Tie - Split pot: {match.matchType.name}',
                        balanceBefore=balanceBefore,
                        balanceAfter=profile.coins
                    )
        
        def awardPot_sync(match, winnerId, replayData=None):
            from django.db import transaction as dbTransaction
            from django.contrib.auth import get_user_model
            import json
            
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
                # Save replay data
                if replayData:
                    participation.replayData = json.dumps(replayData) if not isinstance(replayData, str) else replayData
                participation.save(update_fields=['coinReward', 'placement', 'replayData'])
                
                Transaction.objects.create(
                    user=winner,
                    amount=match.totalPot,
                    transactionType='MATCH_WIN',
                    relatedMatch=match,
                    description=f'Won match: {match.matchType.name}',
                    balanceBefore=balanceBefore,
                    balanceAfter=profile.coins
                )
        
        def completeMatch_sync(match, winnerId):
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
        print(f"[Match {matchId}] Match status updated to IN_PROGRESS, starting engine in background")
        
        # Start engine as background task - don't await it directly
        # This allows the countdown function to complete while the game runs
        asyncio.create_task(engine.start(roomGroupName, handleGameOver))
        print(f"[Match {matchId}] Engine started as background task")
        
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
            
            # Load all existing participants including bots
            participants = await self.getMatchParticipants()
            botColors = [
                '#ef4444', '#f59e0b', '#06b6d4', '#8b5cf6',
                '#ec4899', '#84cc16', '#f97316', '#14b8a6'
            ]
            botColorIdx = 0
            for participant in participants:
                if participant.isBot:
                    botColor = botColors[botColorIdx % len(botColors)]
                    botColorIdx += 1
                    engine.addPlayer(
                        f"bot_{participant.id}",
                        participant.username,
                        botColor,
                        isBot=True
                    )
        
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
        try:
            state = event['state']
            print(f"[GameConsumer {self.matchId}] Sending gameState to client: {state.get('type')}")
            if state.get('type') == 'gameOver':
                print(f"[GameConsumer {self.matchId}] 🏁 Sending GAME OVER to client: winnerId={state.get('winnerId')}, isTie={state.get('isTie')}")
            await self.send(text_data=json.dumps(state))
        except Exception as e:
            import traceback
            print(f"[GameConsumer {self.matchId}] Error in gameState: {e}")
            print(traceback.format_exc())
    
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
    
    @database_sync_to_async
    def getMatchParticipants(self):
        """Get all match participants including bots"""
        return list(MatchParticipation.objects.filter(match_id=self.matchId))