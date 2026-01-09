# Dash - Real-time Multiplayer Bot Arena Game

## Game Overview

**Dash** is a fast-paced, real-time multiplayer game where players control bots on a grid, trying to be the last one standing. Bots move continuously in the direction they're facing, and players can only change direction (UP/DOWN/LEFT/RIGHT). Victory comes from strategic positioning and survival.

### Core Mechanics
- **Continuous Movement:** Bots move automatically in their facing direction at fixed speed
- **Direction Control:** Players change bot direction via keyboard/tap controls
- **Collision Rules:**
  - Touch another bot from side/back → they die
  - Hit a wall → lose coins (in solo) or life (in multiplayer if lives enabled)
  - Hit grid edge → instant death (edges are walls)
- **Dynamic Walls:** Random cells spawn walls (3-second countdown, then permanent)
- **Match Types:** Solo practice mode and multiplayer matchmaking queues

### Game Modes

**Solo Mode:**
- 20×20 grid, single player
- High speed, walls spawn every 3 seconds
- No lives - each wall hit costs coins (deducted from balance)
- Survive as long as possible for coin rewards
- Leaderboard tracks best survival records
- Risk/reward: quit anytime to keep earnings or push for bigger reward

**Multiplayer Matchmaking:**
- Pre-configured match queues (different entry fees, settings)
- Fixed player count per match type (typically 4-8 players)
- Winner takes entire pot (sum of all entry fees)
- Players can force-start with fewer players by paying for empty slots
- No platform cut - winner gets full pot

### Monetization
- **Coin Purchases:** Buy coins with real money (Stripe)
- **Coin Sinks:**
  - Multiplayer match entry fees (5-50+ coins)
  - Bot skins/cosmetics
  - Extra lives for matches (limited per match)
  - Solo mode wall hits (coin penalty)
- **Coin Sources:**
  - Win multiplayer matches
  - Solo mode survival rewards
  - Buy with real money
  - Future: daily admin-organized free tournaments

---

## Django Models Architecture

### **ACCOUNTS APP**

#### **Profile**
- **user** (OneToOneField to User, primaryKey=True)
- **profilePic** (ImageField, nullable)
- **coins** (DecimalField, default=100) - virtual currency balance
- **soloHighScore** (IntegerField, default=0) - walls survived in best solo run
- **totalWins** (IntegerField, default=0) - multiplayer wins
- **totalMatches** (IntegerField, default=0) - matches participated
- **currentSkin** (ForeignKey to BotSkin, nullable) - equipped skin
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
- **livesPerPlayer** (IntegerField, default=0) - 0 means instant death on wall hit
- **wallSpawnInterval** (IntegerField, default=5) - seconds between wall spawns
- **allowExtraLives** (BooleanField, default=False) - can players buy extra lives?
- **maxExtraLives** (IntegerField, default=2)
- **extraLifeCost** (DecimalField, default=5)
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
- **extraLivesPurchased** (IntegerField, default=0)
- **livesRemaining** (IntegerField, default=0)
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
- **playerPositions** (JSONField) - {user_id: {x: int, y: int, direction: str, alive: bool}}
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
- **coinsEarned** (DecimalField, default=0) - reward for surviving
- **coinsLost** (DecimalField, default=0) - penalties for wall hits
- **netCoins** (DecimalField, default=0) - earned - lost
- **survivalTime** (IntegerField) - seconds
- **finalGridState** (JSONField, nullable) - snapshot when died
- **startedAt** (DateTimeField, autoNowAdd=True)
- **endedAt** (DateTimeField, nullable)

---

### **COSMETICS APP**

#### **BotSkin**
Purchasable bot appearance

- **name** (CharField, maxLength=50, unique=True)
- **description** (TextField)
- **previewImage** (ImageField) - shows what skin looks like
- **colorPrimary** (CharField, maxLength=7) - hex color for bot body
- **colorSecondary** (CharField, maxLength=7, nullable) - accent color
- **trailEffect** (CharField, nullable, choices: NONE, GLOW, SPARKLE, FIRE, ICE) - visual trail
- **price** (DecimalField) - coins to purchase
- **isDefault** (BooleanField, default=False) - starter skin (free)
- **rarity** (CharField, choices: COMMON, RARE, EPIC, LEGENDARY)
- **displayOrder** (IntegerField, default=0)
- **createdAt** (DateTimeField, autoNowAdd=True)

#### **OwnedSkin**
Player's owned skins

- **player** (ForeignKey to User, relatedName='ownedSkins')
- **skin** (ForeignKey to BotSkin, relatedName='owners')
- **purchasedAt** (DateTimeField, autoNowAdd=True)
- **uniqueTogether**: (player, skin)

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
- **transactionType** (CharField, choices: PURCHASE, MATCH_ENTRY, MATCH_WIN, SKIN_PURCHASE, SOLO_REWARD, SOLO_PENALTY, EXTRA_LIFE, REFUND)
- **relatedMatch** (ForeignKey to Match, nullable, relatedName='transactions')
- **relatedSkin** (ForeignKey to BotSkin, nullable, relatedName='transactions')
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
6. Server validates, updates positions, checks collisions
7. Broadcast state to all connected clients
8. Last player standing → Match status = COMPLETED, winner gets pot
9. GameState snapshots saved for replay

### Solo Mode Flow
1. Player starts solo run → SoloRun created
2. Game ticks, walls spawn every 3 seconds
3. Wall hit → deduct coins from Profile.coins, increment wallsHit
4. Player quits or dies → calculate rewards, update SoloRun
5. If new high score → update Profile.soloHighScore

### Coin Balance Management
- All coin changes go through Transaction model (audit trail)
- Profile.coins updated atomically (F expressions)
- Cannot go below 0 (validation)

### Matchmaking Queue System
- MatchType defines template
- Match instance created when first player joins
- Players keep joining until `playersRequired` met
- Auto-start or force-start triggers game
- New Match instance created for next queue

---

## Launch Feature Checklist

**MVP (Minimum Viable Product):**
- ✅ Solo mode (practice + coin earning/losing)
- ✅ Multiplayer matchmaking (5-10 match types)
- ✅ Basic bot skins (3-5 skins)
- ✅ Coin purchases via Stripe
- ✅ Leaderboard (solo high scores)
- ✅ Extra lives purchase in matches

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
- Wall hit penalty: -3 coins
- Survival rewards:
  - 10 walls: +5 coins
  - 20 walls: +15 coins
  - 30 walls: +30 coins
  - 40 walls: +50 coins
  - 50+ walls: +75 coins

**Multiplayer Entry Fees:**
- Beginner: 5 coins
- Standard: 10 coins
- Speed: 15 coins
- Arena: 25 coins
- High Stakes: 50 coins

**Cosmetics:**
- Common skins: 20-50 coins
- Rare skins: 100-200 coins
- Epic skins: 300-500 coins
- Legendary skins: 1000+ coins

**Extra Lives:**
- 5 coins per extra life (max 2 per match)

**Coin Packages:**
- Starter: 100 coins - $0.99
- Standard: 500 coins - $4.99
- Premium: 1200 coins - $9.99
- Mega: 3000 coins - $19.99

*Note: All values subject to playtesting and adjustment*
