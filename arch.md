# Dash - Real-time Multiplayer Bot Arena

Fast-paced grid game. Bots auto-move, players change direction. Survive walls, eliminate opponents.

---

## Game Rules

### Solo Mode
- 20×20 grid, walls spawn every 3s
- +1 coin per wall survived, -1 per hit
- Game over at -50 score
- Press ESC to quit and save score

### Multiplayer
- Entry fee required (varies by match type)
- +1 point per wall spawned (all alive players)
- Hits don't reduce score, just count toward elimination (50 hits = out)
- Eliminate opponent → gain their points
- Last standing wins pot (or split if all die)

### Progressive Mode
- Survive and eliminate all bots to advance.
- Each level increases bot count and difficulty.

### Collisions
- Wall/edge hit → +1 hit counter
- Side/back collision → victim eliminated, attacker gains their score
- Head-on collision → both get +1 hit

---

## Tech Stack

Django 5.0 + Channels (WebSocket) + PostgreSQL + Redis + Stripe + Cloudinary

---

## Apps & Implementation

### accounts
**Models:** Profile (coins, stats, profilePic via Cloudinary)

**Views:** Dashboard, login/signup, profile search, picture upload

**Key Choices:**
- Profile auto-created on user signup (post_save signal)
- Coins can go negative (design choice for solo mode)
- Leaderboard sorts by `soloHighScore` (walls survived)
- GET logout allowed (simpler UX than POST)

---

### matches

**Models:**
- MatchType: Pre-configured templates (entry fee, grid size, speed, wallSpawnInterval)
- Match: Instance with status (WAITING → STARTING → IN_PROGRESS → COMPLETED)
- MatchParticipation: Player stats per match
- SoloRun: Solo attempt records (wallsSurvived, wallsHit, replayData)
- ProgressiveRun: Progressive mode records (level, botsEliminated, won, replayData)

**Replay System:**
- Canvas playback with synchronized sound effects
- Frame recording: 150ms per frame, includes player/bot positions, directions, alive status, killerBotIndex
- Death animation: 10-frame explosion at death location, killer bot highlighted with red glow
- Replay limits: Admin-configurable max stored replays (default 50), oldest auto-deleted
- Filtering: Progressive replays filterable by wins/losses, solo/multiplayer show wins only
- Sound fidelity: Web Audio API beeps (move: 400Hz square, hit: 150Hz sawtooth, score: 800Hz sine)

**WebSocket (consumers.py):**
- `GameEngine` class: Server-side game loop
  - Tick rate: 75-200ms based on speed
  - Movement validation: Check boundaries FIRST, then walls, then players
  - Collision detection: New position vs current positions
  - Score tracking: Separate `score` (points) and `hits` (elimination counter)
  - Wall spawning: Based on `wallSpawnInterval` (0 = no walls)
  - Death tracking: Records killerBotIndex when player collision detected
  
**Lobby System:**
- Auto-start: 30s countdown when min players reached
- Force-start: Pay for empty slots to start early
- Countdown persists across page refreshes (localStorage)
- Auto-refresh every 3s to show player count updates

**Views:**
- `joinMatch`: Atomic transaction (deduct fee, add to pot, create participation)
- `forceStart`: Calculate missing slots × entry fee, validate min players
- `leaveLobby`: Refund only if status = WAITING, delete empty matches
- `saveSoloRun`: Calculate net coins, update high score, create transaction records, enforce replay limit
- `saveProgressiveRun`: Deduct entry cost, grant victory rewards (if won), save replay, enforce replay limit
- `browseReplays`: Filter by mode (solo/progressive/multiplayer) and result type (all/wins/losses)
- `watchReplay`: Deduct coins for replay viewing (own = free, others = cost), validate access
- `replayViewer`: Canvas playback with frame-by-frame rendering, death animation, killer bot highlight

**Key Choices:**
- WebSocket for real-time (not polling)
- Server-authoritative (clients send input, server validates)
- Boundary check BEFORE wall check (critical for edge detection)
- One GameEngine instance per match (stored in ACTIVE_GAMES dict)
- Countdown function standalone (doesn't depend on consumer instance)
- Auto-start checks if still WAITING before triggering
- Replays stored as JSON (frameDuration, frames array with all game state)
- Death animation synced to defeat moment, visible for 1500ms before popup

**Client (game.html / gameMultiplayer.html / gameProgressive.html):**
- Canvas rendering with grid + players + walls
- Client-side prediction disabled (wait for server state)
- Keyboard input sent via WebSocket
- Mobile controls: Touch buttons for arrow keys
- Sound effects: Web Audio API (move, hit, score, victory, loss, kill)
- Bot rendering: Arrow-shaped canvas images, rotated by direction
- Death animation: 10-frame explosion, killer bot red glow (150Hz beep on hit)
- Replay recording: Automatic frame capture during gameplay, stored in replayRecorder object

---

### shop

**Models:** CoinPackage, CoinPurchase, Transaction

**Stripe Flow:**
1. `createPaymentIntent`: Create Stripe intent + pending purchase
2. Client confirms payment with card
3. Stripe webhook (`payment_intent.succeeded`) → mark completed, add coins
4. Transaction record created for audit

**Key Choices:**
- Webhook handles fulfillment (not client callback)
- `select_for_update()` prevents double-crediting
- Transaction model logs all coin changes with before/after balance

---

### chat

**Models:** GlobalChatMessage, DirectMessage

**Implementation:**
- HTTP polling every 2s (not WebSocket - simpler)
- `poll` endpoints: Return messages after given ID
- New user gets welcome DM from admin (post_save signal)
- Unread count displayed on dashboard

**Key Choices:**
- Polling over WebSocket (chat not performance-critical)
- Client-side deduplication (track displayed message IDs)
- Auto-scroll only if user at bottom (UX improvement)

---

## Key Flows

### Solo
1. Click start → client-side game loop begins, frame recording starts
2. Walls spawn every 3s (client-side timer)
3. Movement/collision detection (client-side), death animation renders for 1.5s
4. Game ends → POST to `/matches/save-solo-run/` with replay JSON
5. Server validates, updates coins atomically, saves replay, enforces replay limit, returns new balance
6. User can browse/watch replays with synchronized sounds and game state

### Multiplayer
1. Join → deduct fee, add to WAITING match
2. Min players → 30s countdown (localStorage persists across refreshes)
3. Time's up OR force-start → status = STARTING
4. 10s countdown broadcast via WebSocket
5. Status = IN_PROGRESS → GameEngine.start(), frame recording starts
6. Game loop: tick → validate → broadcast state
7. Player eliminated → death animation plays, killer bot highlighted red
8. Last alive → end game, award pot, update stats, save replay
9. User can watch winning replay with death animations for defeats

### Progressive
1. Click level → deduct entry cost, initialize game, start frame recording
2. Survive and eliminate all bots for current level → advance or end game
3. Death or level completion → death animation plays (if defeated), POST to `/matches/save-progressive-run/`
4. Server saves as win or loss, grants rewards if won, enforces replay limit
5. Browse replays filtered by wins/losses, watch with killer bot highlight and death animation
6. Track personal best (highest level reached)

---

## Data Integrity

- All coin operations: Atomic with `select_for_update()` + `F()` expressions
- Transaction audit trail: Every coin change logged
- Refunds: Only when match status = WAITING
- Match cleanup: Delete if currentPlayers = 0 after leave

---

## Setup

```bash
pip install -r requirements.txt
# .env: DATABASE_URL, REDIS_URL, STRIPE_*, CLOUDINARY_*
python manage.py migrate
python manage.py createsuperuser
# Create MatchTypes via admin panel
daphne -b 0.0.0.0 -p 8000 project.asgi:application
```