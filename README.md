# Dash - Multiplayer Bot Arena Game
[Stable](https://dash.vicnas.me)
[Preview](https://dash0.up.railway.app)

## Game Rules

### Core Mechanics
- Bots move continuously in their facing direction
- Players change direction with arrow keys/WASD
- Walls spawn periodically with 3-second countdown

### Solo Mode Scoring
- **+1 coin** per wall spawned (walls you survive)
- **-1 coin** per wall/edge hit
- **Game over** when score reaches -50
- No entry fee - your final score (positive or negative) is added to your coin balance
- Can quit anytime to save current score
- Walls spawn every 3 seconds

### Multiplayer Scoring
- **Entry fee required** - no additional losses beyond this
- **+1 point** per wall spawned (all alive players)
- **Wall/edge hits DON'T reduce score** - they count toward elimination
- **Eliminated at 50 hits** or when hit by another player
- **Eliminate another player** → gain their points (minimum 0)
- **Last player standing** wins entire pot
- Walls spawn every 5 seconds / no walls

### Progressive Mode
Progressive mode is a solo challenge where you face more bots each level. Survive and eliminate all bots to progress. Each level bring one more bot. 

**Rules:**
- Survive and eliminate all bots to advance.
- Each level increases bot count and difficulty.

### Player Interactions
- **Side/back collision**: Attacker eliminates victim, gains their score
- **Head-on collision**: Both players get a hit (may eliminate both if at 50 hits)

---

## Tech Stack

- Django 5.0 + Channels (WebSockets)
- PostgreSQL + Redis
- Stripe payments
- Cloudinary storage

---

## Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
STRIPE_SECRET_KEY=...
CLOUDINARY_CLOUD_NAME=...

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run server
daphne -b 0.0.0.0 -p 8000 project.asgi:application
```

---

## Apps

### accounts
User profiles, coins, stats

### matches
Solo/multiplayer games, matchmaking, scoring

### shop
Coin packages, Stripe integration

### chat
Direct messages + global chat

---

## Game Modes

### Solo Practice
- 20×20 grid, single player
- High speed, walls spawn every 3 seconds
- **Scoring:**
  - **+1 coin** per wall spawned
  - **-1 coin** per wall/edge hit
  - Game ends at **-50 coins**
- No entry fee
- Final score (can be negative) added to balance
- Track high score on leaderboard

### Multiplayer Matchmaking
- Pre-configured match types with different entry fees
- Fixed player count per match type (4-8 players)
- Winner takes entire pot
- **Scoring:**
  - **+1 point** per wall spawned (all alive players)
  - Wall/edge hits **don't reduce score**
  - Eliminated at **50 hits** total
  - **+opponent's points** when eliminating them
- Last player standing wins
- Players can force-start by paying for empty slots

---

## Protection
- Free for personal/educational use
- No commercial use without permission
