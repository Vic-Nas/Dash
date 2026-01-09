# Dash - Real-time Multiplayer Bot Arena Game

## Game Overview

**Dash** is a fast-paced, real-time multiplayer game where players control bots on a grid, trying to be the last one standing. Bots move continuously in the direction they're facing, and players can only change direction (UP/DOWN/LEFT/RIGHT). Victory comes from strategic positioning, survival, and scoring points.

### Core Mechanics
- **Continuous Movement:** Bots move automatically in their facing direction at fixed speed
- **Direction Control:** Players change bot direction via keyboard/tap controls
- **Scoring System:**
  - **+1 point** for each wall that successfully spawns on the grid
  - **-1 point** for hitting a wall or edge
  - Score starts at 0 and can go negative
- **Collision Rules:**
  - **Solo Mode:** Hit wall/edge → lose 1 point. Game over at -50 points
  - **Multiplayer:** Hit wall/edge → lose 1 point. Hit another player from side/back → they're eliminated and you gain their score (minimum 0). Game over at -50 points OR when eliminated by another player
- **Dynamic Walls:** Random cells spawn walls (3-second countdown, then permanent)
- **Match Types:** Solo practice mode and multiplayer matchmaking queues

### Game Modes

**Solo Mode:**
- 20×20 grid, single player
- High speed, walls spawn every 3 seconds
- **Scoring:**
  - **+1 coin** per wall spawned (walls you survive)
  - **-1 coin** per wall/edge hit
  - Game ends when score reaches **-50 coins**
- No entry fee - score translates directly to coin gain/loss
- Survive as long as possible and build your score
- Leaderboard tracks best survival records (walls survived)
- Can quit anytime to save current score

**Multiplayer Matchmaking:**
- Pre-configured match queues (different entry fees, settings)
- Fixed player count per match type (typically 4-8 players)
- Winner takes entire pot (sum of all entry fees)
- **Scoring:**
  - **+1 point** per wall spawned (for all alive players)
  - **-1 point** per wall/edge hit
  - **+opponent's score** (minimum 0) when eliminating another player
  - Eliminated at -50 points OR when hit by another player from side/back
- Last player standing wins the pot
- Players can force-start with fewer players by paying for empty slots
- No platform cut - winner gets full pot

### Collision & Elimination Details

**Solo Mode:**
- Hitting walls or edges deducts 1 point from your score
- Game over when your score reaches -50
- Your final score (positive or negative) is added to your coin balance

**Multiplayer:**
- **Wall/Edge Hit:** -1 point, continue playing unless score reaches -50
- **Hit Another Player (Side/Back):**
  - Victim is immediately eliminated from the match
  - Attacker gains victim's score (if positive) or gains 0 (if victim's score is negative)
  - Example: If you have +5 points and eliminate someone with +10 points, you now have +15 points
  - Example: If you have +5 points and eliminate someone with -3 points, you still have +5 points (can't gain from negative scores)
- **Head-On Collision:** Both players are eliminated
- **Score of -50:** Eliminated even if not hit by another player
- Last player alive wins the entire pot

---

## Django Models Architecture

### **ACCOUNTS APP**

#### **Profile**
- **user** (OneToOneField to User, primaryKey=True)
- **profilePic** (ImageField, nullable)
- **coins** (DecimalField, default=100) - virtual currency balance (can go negative)
- **soloHighScore** (IntegerField, default=0) - walls survived in best solo run
- **totalWins** (IntegerField, default=0) - multiplayer wins
- **totalMatches** (IntegerField, default=0) - matches participated
- **createdAt** (DateTimeField, autoNowAdd=True)
- **isActive** (BooleanField, default=True)
- **activityLog** (TextField, default="")

---

### **MATCHES APP**

#### **MatchType**
Pre-configured match templates that players can join

- **name** (CharField, maxLength=50, unique=True) - e.g., "Quick Match", "Speed Demon"
- **description** (TextField)
- **entryFee** (DecimalField) - coins to enter
- **gridSize** (IntegerField) - grid side length (20, 25, 30, etc.)
- **speed** (CharField, choices: SLOW, MEDIUM, FAST, EXTREME)
- **playersRequired** (IntegerField) - players needed to auto-start
- **maxPlayers** (IntegerField) - maximum allowed
- **wallSpawnInterval** (IntegerField, default=5) - seconds between wall spawns
- **isActive** (BooleanField, default=True) - visible in matchmaking?
- **displayOrder** (IntegerField, default=0)
- **createdAt** (DateTimeField, autoNowAdd=True)

#### **Match**
Active or completed match instance

- **matchType** (ForeignKey to MatchType, relatedName='matches')
- **status** (CharField, choices: WAITING, STARTING, IN_PROGRESS, COMPLETED, CANCELLED)
- **gridSize** (IntegerField) - snapshot from matchType
- **speed** (CharField) - snapshot from matchType
- **currentPlayers** (IntegerField, default=0) - players currently joined
- **playersRequired** (IntegerField) - snapshot from matchType
- **totalPot** (DecimalField, default=0) - total coins in pot
- **winner** (ForeignKey to User, nullable, relatedName='matchesWon')
- **forceStartedBy** (ForeignKey to User, nullable, relatedName='forcedMatches') - who paid to force start
- **startedAt** (DateTimeField, nullable)
- **completedAt** (DateTimeField, nullable)
- **createdAt** (DateTimeField, autoNowAdd=True)
- **isSoloMode** (BooleanField, default=False)

#### **MatchParticipation**
Player's participation in a match

- **match** (ForeignKey to Match, relatedName='participants')
- **player** (ForeignKey to User, relatedName='matchParticipations')
- **entryFeePaid** (DecimalField) - coins paid to enter
- **placement** (IntegerField, nullable) - 1st, 2nd, 3rd, etc.
- **wallsHit** (IntegerField, default=0)
- **botsEliminated** (IntegerField, default=0) - how many others they killed
- **survivalTime** (IntegerField, nullable) - seconds survived
- **coinReward** (DecimalField, default=0) - coins won (0 if not winner)
- **joinedAt** (DateTimeField, autoNowAdd=True)
- **eliminatedAt** (DateTimeField, nullable)
- **uniqueTogether**: (match, player)

#### **GameState**
Real-time game state for active matches (stored for replay/spectating)

- **match** (ForeignKey to Match, relatedName='gameStates')
- **tickNumber** (IntegerField) - game tick counter
- **timestamp** (DateTimeField, autoNowAdd=True)
- **playerPositions** (JSONField) - {user_id: {x: int, y: int, direction: str, alive: bool, score: int}}
- **walls** (JSONField) - [{x: int, y: int}] - list of wall positions
- **countdownWalls** (JSONField) - [{x: int, y: int, secondsLeft: int}] - walls spawning
- **activePlayers** (IntegerField) - players still alive
- **ordering**: ['tickNumber']

**Note:** GameStates stored periodically (every 10 ticks?) for replay, not every single tick

#### **SoloRun**
Individual solo mode attempt

- **player** (ForeignKey to User, relatedName='soloRuns')
- **wallsSurvived** (IntegerField, default=0)
- **wallsHit** (IntegerField, default=0)
- **coinsEarned** (DecimalField, default=0) - +1 per wall survived
- **coinsLost** (DecimalField, default=0) - -1 per wall hit
- **netCoins** (DecimalField, default=0) - earned - lost
- **survivalTime** (IntegerField) - seconds
- **finalGridState** (JSONField, nullable) - snapshot when died
- **startedAt** (DateTimeField, autoNowAdd=True)
- **endedAt** (DateTimeField, nullable)

---

### **SHOP APP**

#### **CoinPackage**
Real money → coins offers

- **name** (CharField, maxLength=100) - e.g., "Starter Pack", "Mega Bundle"
- **description** (TextField, nullable)
- **coins** (IntegerField) - amount of coins
- **price** (DecimalField) - USD price
- **displayOrder** (IntegerField, default=0)
- **iconImage** (ImageField, nullable)
- **isActive** (BooleanField, default=True)
- **createdAt** (DateTimeField, autoNowAdd=True)

#### **CoinPurchase**
Purchase transaction record

- **user** (ForeignKey to User, relatedName='coinPurchases')
- **package** (ForeignKey to CoinPackage, relatedName='purchases')
- **stripePaymentIntentId** (CharField, unique=True)
- **status** (CharField, choices: PENDING, COMPLETED, FAILED, REFUNDED)
- **coinAmount** (IntegerField) - snapshot
- **pricePaid** (DecimalField) - snapshot
- **createdAt** (DateTimeField, autoNowAdd=True)
- **completedAt** (DateTimeField, nullable)

#### **Transaction**
All coin movements (audit log)

- **user** (ForeignKey to User, relatedName='transactions')
- **amount** (DecimalField) - positive = gained, negative = spent
- **transactionType** (CharField, choices: PURCHASE, MATCH_ENTRY, MATCH_WIN, SOLO_REWARD, SOLO_PENALTY, EXTRA_LIFE, REFUND)
- **relatedMatch** (ForeignKey to Match, nullable, relatedName='transactions')
- **description** (CharField, maxLength=255)
- **balanceBefore** (DecimalField)
- **balanceAfter** (DecimalField)
- **createdAt** (DateTimeField, autoNowAdd=True)

---

## Grid Formula & Spawn Logic

### Grid Size Based on Players
- **gridSize = 15 + (maxPlayers × 2.5)**, rounded to nearest 5
- Examples:
  - 4 players → 25×25
  - 6 players → 30×30
  - 8 players → 35×35

### Player Spawn Positions
Players spawn evenly around grid perimeter:
- Calculate perimeter: `4 × gridSize`
- Spacing: `perimeter / numPlayers`
- Walk around edge placing players at intervals
- All face toward center initially (or random directions)

### Wall Spawn Logic
- Every `wallSpawnInterval` seconds, pick random empty cell
- Show 3-second countdown on that cell
- After countdown, cell becomes permanent wall
- **All alive players gain +1 point when wall spawns**
- Continue until match ends

---

## Technical Implementation Notes

### Real-time Architecture
- **Django Channels** for WebSocket connections
- **ASGI server** (Daphne/Uvicorn)
- **Redis** as channel layer backend
- Each match runs async game loop (ticks every 100-200ms)
- Game state broadcasted to all players + spectators

### Match Flow
1. Player joins queue → MatchParticipation created, coins deducted
2. When `playersRequired` reached → Match status = STARTING (5 sec countdown)
3. Or player force-starts → pays for missing slots, immediate start
4. Match begins → game loop starts ticking
5. Players send direction inputs via WebSocket
6. Server validates, updates positions, checks collisions, tracks scores
7. Broadcast state to all connected clients
8. Last player standing → Match status = COMPLETED, winner gets pot
9. GameState snapshots saved for replay

### Solo Mode Flow
1. Player starts solo run → SoloRun created
2. Game ticks, walls spawn every 3 seconds
3. Wall spawns → player gains +1 point
4. Wall/edge hit → player loses -1 point
5. Score reaches -50 OR player quits → calculate rewards, update SoloRun
6. Net score added to Profile.coins (can go negative)
7. If new high score → update Profile.soloHighScore

### Coin Balance Management
- All coin changes go through Transaction model (audit trail)
- Profile.coins updated atomically (F expressions)
- Balance CAN go negative (unlike previous version)

### Matchmaking Queue System
- MatchType defines template
- Match instance created when first player joins
- Players keep joining until `playersRequired` met
- Auto-start or force-start triggers game
- New Match instance created for next queue

---

## Launch Feature Checklist

**MVP (Minimum Viable Product):**
- ✅ Solo mode (practice + coin earning/losing based on score)
- ✅ Multiplayer matchmaking (5-10 match types)
- ✅ Basic bot skins (3-5 skins)
- ✅ Coin purchases via Stripe
- ✅ Leaderboard (solo high scores)
- ✅ Score-based elimination system

**Post-Launch:**
- Daily admin-organized free tournaments
- More cosmetics (death effects, victory emotes, trails)
- Replay system (watch past matches)
- Spectator mode (watch live matches)
- Friend challenges
- Seasons/rankings
- Achievements

---

## Economy Balance (Initial Values)

**Solo Mode:**
- Wall spawned: +1 coin
- Wall/edge hit: -1 coin
- Game over: Score reaches -50
- Net score added to balance (can go negative)

**Multiplayer Entry Fees:**
- Beginner: 5 coins
- Standard: 10 coins
- Speed: 15 coins
- Arena: 25 coins
- High Stakes: 50 coins

**Coin Packages:**
- Starter: 100 coins - $0.99
- Standard: 500 coins - $4.99
- Premium: 1200 coins - $9.99
- Mega: 3000 coins - $19.99

*Note: All values subject to playtesting and adjustment*