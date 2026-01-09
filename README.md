# Dash - Multiplayer Bot Arena Game

## Game Rules

### Core Mechanics
- Bots move continuously in their facing direction
- Players change direction with arrow keys/WASD
- Walls spawn every 3 seconds with countdown

### Scoring
- **+1 point** when a wall spawns (all alive players)
- **-1 point** when hitting wall or edge
- **Eliminate player from side/back** → gain their score (min 0)
- **Game over** at -50 points or when eliminated

### Solo Mode
- Score = coins gained/lost
- Game ends at -50 coins
- No entry fee

### Multiplayer
- Entry fee required
- Winner takes full pot
- Last player standing wins

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

### chat (new)
Direct messages + global chat

## Protection
- Free for personal/educational use

- No commercial use without permission