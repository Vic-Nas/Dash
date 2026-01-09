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

# Active games {match_id: GameEngine instance}
ACTIVE_GAMES = {}

class GameEngine:
    def __init__(self, match_id, grid_size, speed, lives_per_player):
        self.match_id = match_id
        self.grid_size = grid_size
        self.speed = speed
        self.lives_per_player = lives_per_player
        
        # Speed to tick rate mapping (ms)
        speed_map = {'SLOW': 200, 'MEDIUM': 150, 'FAST': 100, 'EXTREME': 75}
        self.tick_rate = speed_map.get(speed, 150) / 1000  # Convert to seconds
        
        self.players = {}  # {user_id: {x, y, direction, alive, lives, username, playerColor, skinName}}
        self.walls = []
        self.countdown_walls = []
        self.tick_number = 0
        self.running = False
        self.task = None
        self.wall_spawn_task = None
        
        # Player identification colors
        self.available_colors = [
            '#5b7bff', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', 
            '#06b6d4', '#ef4444', '#84cc16', '#f97316', '#14b8a6'
        ]
    
    def add_player(self, user_id, username, skin_name, player_color):
        if user_id in self.players:
            return
        
        # Spawn at random position
        x = random.randint(1, self.grid_size - 2)
        y = random.randint(1, self.grid_size - 2)
        
        self.players[user_id] = {
            'username': username,
            'x': x,
            'y': y,
            'direction': random.choice(['UP', 'DOWN', 'LEFT', 'RIGHT']),
            'alive': True,
            'lives': self.lives_per_player,
            'playerColor': player_color,  # Color for player identification
            'skinName': skin_name  # Which skin asset to use
        }
    
    def update_direction(self, user_id, direction):
        if user_id in self.players and self.players[user_id]['alive']:
            self.players[user_id]['direction'] = direction
    
    def tick(self):
        self.tick_number += 1
        
        # Move all alive players
        for user_id, player in self.players.items():
            if not player['alive']:
                continue
            
            new_x, new_y = player['x'], player['y']
            
            if player['direction'] == 'UP':
                new_y -= 1
            elif player['direction'] == 'DOWN':
                new_y += 1
            elif player['direction'] == 'LEFT':
                new_x -= 1
            elif player['direction'] == 'RIGHT':
                new_x += 1
            
            # Check edge collision - treat as wall hit
            if new_x < 0 or new_x >= self.grid_size or new_y < 0 or new_y >= self.grid_size:
                self.handle_collision(user_id)
                continue
            
            # Check wall collision
            if any(w['x'] == new_x and w['y'] == new_y for w in self.walls):
                self.handle_collision(user_id)
                continue
            
            # Check player collision (from side/back = other dies, head-on = both die)
            for other_id, other in self.players.items():
                if other_id != user_id and other['alive']:
                    if other['x'] == new_x and other['y'] == new_y:
                        # Both players collide head-on
                        self.handle_collision(user_id)
                        self.handle_collision(other_id)
                        continue
            
            # Valid move
            player['x'] = new_x
            player['y'] = new_y
    
    def handle_collision(self, user_id):
        player = self.players[user_id]
        
        if self.lives_per_player == 0:
            # Instant death mode
            player['alive'] = False
        else:
            # Lives mode
            player['lives'] -= 1
            if player['lives'] <= 0:
                player['alive'] = False
    
    def spawn_wall(self):
        attempts = 0
        while attempts < 100:
            x = random.randint(0, self.grid_size - 1)
            y = random.randint(0, self.grid_size - 1)
            
            # Check if position is occupied
            occupied = any(w['x'] == x and w['y'] == y for w in self.walls)
            occupied = occupied or any(w['x'] == x and w['y'] == y for w in self.countdown_walls)
            occupied = occupied or any(p['x'] == x and p['y'] == y and p['alive'] for p in self.players.values())
            
            if not occupied:
                self.countdown_walls.append({'x': x, 'y': y, 'seconds_left': 3})
                break
            
            attempts += 1
    
    def update_countdown_walls(self):
        to_remove = []
        for wall in self.countdown_walls:
            wall['seconds_left'] -= 1
            if wall['seconds_left'] <= 0:
                self.walls.append({'x': wall['x'], 'y': wall['y']})
                to_remove.append(wall)
        
        for wall in to_remove:
            self.countdown_walls.remove(wall)
    
    def get_state(self):
        return {
            'tick': self.tick_number,
            'players': self.players,
            'walls': self.walls,
            'countdown_walls': self.countdown_walls,
            'alive_count': sum(1 for p in self.players.values() if p['alive'])
        }
    
    def check_game_over(self):
        alive = [uid for uid, p in self.players.items() if p['alive']]
        if len(alive) <= 1:
            return alive[0] if alive else None
        return None
    
    async def start(self, broadcast_callback):
        self.running = True
        
        # Main game loop
        async def game_loop():
            while self.running:
                self.tick()
                await broadcast_callback(self.get_state())
                
                winner_id = self.check_game_over()
                if winner_id is not None:
                    await self.end_game(winner_id, broadcast_callback)
                    break
                
                await asyncio.sleep(self.tick_rate)
        
        # Wall countdown loop
        async def countdown_loop():
            while self.running:
                await asyncio.sleep(1)
                self.update_countdown_walls()
        
        # Wall spawn loop
        async def spawn_loop():
            while self.running:
                await asyncio.sleep(3)
                self.spawn_wall()
        
        self.task = asyncio.create_task(game_loop())
        self.wall_spawn_task = asyncio.create_task(spawn_loop())
        asyncio.create_task(countdown_loop())
    
    async def end_game(self, winner_id, broadcast_callback):
        self.running = False
        
        # Determine if it's a tie
        alive_players = [uid for uid, p in self.players.items() if p['alive']]
        is_tie = len(alive_players) == 0
        
        await broadcast_callback({
            'type': 'game_over',
            'winner_id': winner_id if not is_tie else None,
            'winner_username': self.players[winner_id]['username'] if winner_id and not is_tie else None,
            'is_tie': is_tie,
            'alive_players': alive_players
        })
    
    def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
        if self.wall_spawn_task:
            self.wall_spawn_task.cancel()


class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.match_id = self.scope['url_route']['kwargs']['match_id']
        self.room_group_name = f'match_{self.match_id}'
        self.user = self.scope['user']
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Check if player is in this match
        participation = await self.get_participation()
        if not participation:
            await self.close()
            return
        
        # Get player's skin and assigned color
        player_data = await self.get_player_data()
        
        # Get or create game engine
        if self.match_id not in ACTIVE_GAMES:
            match = await self.get_match()
            engine = GameEngine(
                self.match_id,
                match.gridSize,
                match.speed,
                match.matchType.livesPerPlayer
            )
            ACTIVE_GAMES[self.match_id] = engine
        
        engine = ACTIVE_GAMES[self.match_id]
        
        # Add player with their skin and color
        engine.add_player(
            self.user.id,
            self.user.username,
            player_data['skinName'],
            player_data['playerColor']
        )
        
        # Send player their assigned color
        await self.send(text_data=json.dumps({
            'type': 'player_color',
            'playerColor': player_data['playerColor']
        }))
        
        # If match should start, start it
        match = await self.get_match()
        if match.status == 'STARTING' and not engine.running:
            await self.start_match()
            await engine.start(self.broadcast_state)
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        
        if action == 'change_direction':
            direction = data.get('direction')
            if direction in ['UP', 'DOWN', 'LEFT', 'RIGHT']:
                engine = ACTIVE_GAMES.get(self.match_id)
                if engine:
                    engine.update_direction(self.user.id, direction)
    
    async def game_state(self, event):
        await self.send(text_data=json.dumps(event['state']))
    
    async def broadcast_state(self, state):
        # Handle game over
        if state.get('type') == 'game_over':
            await self.handle_game_over(state)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_state',
                'state': state
            }
        )
    
    async def handle_game_over(self, state):
        """Handle game over - award pot to winner(s)"""
        match = await self.get_match()
        
        is_tie = state.get('is_tie', False)
        winner_id = state.get('winner_id')
        
        if is_tie:
            await self.split_pot(match)
        elif winner_id:
            await self.award_pot(match, winner_id)
        
        await self.complete_match(match, winner_id)
    
    @database_sync_to_async
    def get_player_data(self):
        """Get player's equipped skin and assign a color"""
        from cosmetics.models import BotSkin
        
        profile = self.user.profile
        
        # Get skin name
        if profile.currentSkin:
            skin_name = profile.currentSkin.name
        else:
            # Get default skin
            default_skin = BotSkin.objects.filter(isDefault=True).first()
            skin_name = default_skin.name if default_skin else 'Default'
        
        # Get participation to find/assign color
        participation = MatchParticipation.objects.get(
            match_id=self.match_id,
            player=self.user
        )
        
        # Assign color based on join order
        match = Match.objects.get(id=self.match_id)
        all_participants = list(match.participants.order_by('joinedAt').values_list('player_id', flat=True))
        player_index = all_participants.index(self.user.id)
        
        colors = [
            '#5b7bff', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', 
            '#06b6d4', '#ef4444', '#84cc16', '#f97316', '#14b8a6'
        ]
        player_color = colors[player_index % len(colors)]
        
        return {
            'skinName': skin_name,
            'playerColor': player_color
        }
    
    @database_sync_to_async
    def split_pot(self, match):
        """Split pot equally among all participants"""
        from django.db import transaction as db_transaction
        
        with db_transaction.atomic():
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
    def award_pot(self, match, winner_id):
        """Award full pot to winner"""
        from django.db import transaction as db_transaction
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        with db_transaction.atomic():
            match = Match.objects.select_for_update().get(id=match.id)
            winner = User.objects.get(id=winner_id)
            
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
    def complete_match(self, match, winner_id):
        """Mark match as completed"""
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        match.status = 'COMPLETED'
        match.completedAt = timezone.now()
        if winner_id:
            match.winner = User.objects.get(id=winner_id)
        match.save(update_fields=['status', 'completedAt', 'winner'])
        
        for participation in match.participants.select_related('player__profile').all():
            profile = participation.player.profile
            profile.totalMatches = F('totalMatches') + 1
            profile.save(update_fields=['totalMatches'])
    
    @database_sync_to_async
    def get_participation(self):
        try:
            return MatchParticipation.objects.get(
                match_id=self.match_id,
                player=self.user
            )
        except MatchParticipation.DoesNotExist:
            return None
    
    @database_sync_to_async
    def get_match(self):
        return Match.objects.select_related('matchType').get(id=self.match_id)
    
    @database_sync_to_async
    def start_match(self):
        match = Match.objects.get(id=self.match_id)
        match.status = 'IN_PROGRESS'
        match.startedAt = timezone.now()
        match.save()