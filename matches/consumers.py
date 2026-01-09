import json
import asyncio
import random
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Match, MatchParticipation
from decimal import Decimal

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
        
        self.players = {}  # {user_id: {x, y, direction, alive, lives, color}}
        self.walls = []
        self.countdown_walls = []
        self.tick_number = 0
        self.running = False
        self.task = None
        self.wall_spawn_task = None
        
        # Color palette for player backgrounds
        self.available_colors = [
            '#1a1d35', '#1a2332', '#2d1b2e', '#1f2937', '#172430',
            '#2a1a2e', '#1e3a3a', '#2e1a1a', '#1a2e1a', '#2e2a1a'
        ]
    
    def add_player(self, user_id, username):
        if user_id in self.players:
            return
        
        # Assign random color
        color = random.choice(self.available_colors)
        if color in [p['color'] for p in self.players.values()]:
            # Try to get unique color
            unused = [c for c in self.available_colors if c not in [p['color'] for p in self.players.values()]]
            if unused:
                color = random.choice(unused)
        
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
            'color': color
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
                if winner_id:
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
                await asyncio.sleep(3)  # Spawn every 3 seconds
                self.spawn_wall()
        
        self.task = asyncio.create_task(game_loop())
        self.wall_spawn_task = asyncio.create_task(spawn_loop())
        asyncio.create_task(countdown_loop())
    
    async def end_game(self, winner_id, broadcast_callback):
        self.running = False
        await broadcast_callback({
            'type': 'game_over',
            'winner_id': winner_id,
            'winner_username': self.players[winner_id]['username'] if winner_id else 'None'
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
        engine.add_player(self.user.id, self.user.username)
        
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
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_state',
                'state': state
            }
        )
    
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