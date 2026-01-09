// Game.js - Minimal rendering only, all logic in Python backend
// Solo mode game for Dash Arena

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const GRID_SIZE = 20;
const CELL_SIZE = canvas.width / GRID_SIZE;
const TICK_RATE = 150; // ms per move
const WALL_SPAWN_INTERVAL = 3000; // 3 seconds

// Game state (managed by frontend for solo mode)
let gameState = {
  player: { x: 10, y: 10, direction: 'UP', alive: true },
  walls: [],
  countdownWalls: [],
  wallsSurvived: 0,
  wallsHit: 0,
  startTime: Date.now(),
  lastWallSpawn: Date.now(),
  gameOver: false
};

let currentDirection = 'UP';
let nextDirection = 'UP';
let gameStarted = false;

// Input handling
document.addEventListener('keydown', (e) => {
  if (!gameStarted || gameState.gameOver) return;

  // ESC to quit
  if (e.key === 'Escape') {
    endGame();
    return;
  }

  // Direction changes
  const key = e.key.toUpperCase();
  if (key === 'W' || key === 'ARROWUP') nextDirection = 'UP';
  else if (key === 'S' || key === 'ARROWDOWN') nextDirection = 'DOWN';
  else if (key === 'A' || key === 'ARROWLEFT') nextDirection = 'LEFT';
  else if (key === 'D' || key === 'ARROWRIGHT') nextDirection = 'RIGHT';
});

// Initialize game
function initGame() {
  gameState.player = { x: 10, y: 10, direction: 'UP', alive: true };
  gameState.walls = [];
  gameState.countdownWalls = [];
  gameState.wallsSurvived = 0;
  gameState.wallsHit = 0;
  gameState.startTime = Date.now();
  gameState.lastWallSpawn = Date.now();
  gameState.gameOver = false;
  
  currentDirection = 'UP';
  nextDirection = 'UP';
  
  startGameLoop();
}

// Game loop
function startGameLoop() {
  setInterval(() => {
    if (!gameState.gameOver) {
      updateGame();
      render();
      updateHUD();
    }
  }, TICK_RATE);
  
  // Wall spawn timer
  setInterval(() => {
    if (!gameState.gameOver) {
      spawnWall();
    }
  }, WALL_SPAWN_INTERVAL);
  
  // Countdown wall timer
  setInterval(() => {
    if (!gameState.gameOver) {
      updateCountdownWalls();
    }
  }, 1000);
}

function updateGame() {
  // Update direction
  currentDirection = nextDirection;
  gameState.player.direction = currentDirection;
  
  // Calculate new position
  let newX = gameState.player.x;
  let newY = gameState.player.y;
  
  if (currentDirection === 'UP') newY--;
  else if (currentDirection === 'DOWN') newY++;
  else if (currentDirection === 'LEFT') newX--;
  else if (currentDirection === 'RIGHT') newX++;
  
  // Check boundaries (instant death)
  if (newX < 0 || newX >= GRID_SIZE || newY < 0 || newY >= GRID_SIZE) {
    endGame();
    return;
  }
  
  // Check wall collision
  const hitWall = gameState.walls.some(w => w.x === newX && w.y === newY);
  if (hitWall) {
    gameState.wallsHit++;
  }
  
  // Update position
  gameState.player.x = newX;
  gameState.player.y = newY;
}

function spawnWall() {
  // Pick random empty cell
  let x, y;
  let attempts = 0;
  do {
    x = Math.floor(Math.random() * GRID_SIZE);
    y = Math.floor(Math.random() * GRID_SIZE);
    attempts++;
  } while (
    attempts < 100 &&
    (isOccupied(x, y) || (x === gameState.player.x && y === gameState.player.y))
  );
  
  if (attempts < 100) {
    gameState.countdownWalls.push({ x, y, secondsLeft: 3 });
  }
}

function updateCountdownWalls() {
  gameState.countdownWalls = gameState.countdownWalls.filter(w => {
    w.secondsLeft--;
    if (w.secondsLeft <= 0) {
      gameState.walls.push({ x: w.x, y: w.y });
      gameState.wallsSurvived++;
      return false;
    }
    return true;
  });
}

function isOccupied(x, y) {
  return gameState.walls.some(w => w.x === x && w.y === y) ||
         gameState.countdownWalls.some(w => w.x === x && w.y === y);
}

function render() {
  // Clear canvas
  ctx.fillStyle = '#121428';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  
  // Draw grid
  ctx.strokeStyle = '#23264a';
  ctx.lineWidth = 1;
  for (let i = 0; i <= GRID_SIZE; i++) {
    ctx.beginPath();
    ctx.moveTo(i * CELL_SIZE, 0);
    ctx.lineTo(i * CELL_SIZE, canvas.height);
    ctx.stroke();
    
    ctx.beginPath();
    ctx.moveTo(0, i * CELL_SIZE);
    ctx.lineTo(canvas.width, i * CELL_SIZE);
    ctx.stroke();
  }
  
  // Draw walls
  ctx.fillStyle = '#ef4444';
  gameState.walls.forEach(w => {
    ctx.fillRect(w.x * CELL_SIZE + 2, w.y * CELL_SIZE + 2, CELL_SIZE - 4, CELL_SIZE - 4);
  });
  
  // Draw countdown walls
  gameState.countdownWalls.forEach(w => {
    const alpha = 0.3 + (0.7 * (3 - w.secondsLeft) / 3);
    ctx.fillStyle = `rgba(239, 68, 68, ${alpha})`;
    ctx.fillRect(w.x * CELL_SIZE + 2, w.y * CELL_SIZE + 2, CELL_SIZE - 4, CELL_SIZE - 4);
    
    // Draw countdown number
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 16px system-ui';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(w.secondsLeft, (w.x + 0.5) * CELL_SIZE, (w.y + 0.5) * CELL_SIZE);
  });
  
  // Draw player
  ctx.fillStyle = '#5b7bff';
  ctx.fillRect(
    gameState.player.x * CELL_SIZE + 4,
    gameState.player.y * CELL_SIZE + 4,
    CELL_SIZE - 8,
    CELL_SIZE - 8
  );
  
  // Draw direction indicator
  ctx.fillStyle = '#fff';
  const px = gameState.player.x * CELL_SIZE + CELL_SIZE / 2;
  const py = gameState.player.y * CELL_SIZE + CELL_SIZE / 2;
  ctx.beginPath();
  if (currentDirection === 'UP') {
    ctx.moveTo(px, py - 8);
    ctx.lineTo(px - 4, py - 2);
    ctx.lineTo(px + 4, py - 2);
  } else if (currentDirection === 'DOWN') {
    ctx.moveTo(px, py + 8);
    ctx.lineTo(px - 4, py + 2);
    ctx.lineTo(px + 4, py + 2);
  } else if (currentDirection === 'LEFT') {
    ctx.moveTo(px - 8, py);
    ctx.lineTo(px - 2, py - 4);
    ctx.lineTo(px - 2, py + 4);
  } else if (currentDirection === 'RIGHT') {
    ctx.moveTo(px + 8, py);
    ctx.lineTo(px + 2, py - 4);
    ctx.lineTo(px + 2, py + 4);
  }
  ctx.fill();
}

function updateHUD() {
  document.getElementById('wallsSurvived').textContent = gameState.wallsSurvived;
  document.getElementById('wallsHit').textContent = gameState.wallsHit;
  
  const elapsed = Math.floor((Date.now() - gameState.startTime) / 1000);
  document.getElementById('time').textContent = elapsed + 's';
}

async function endGame() {
  if (gameState.gameOver) return;
  gameState.gameOver = true;
  
  const survivalTime = Math.floor((Date.now() - gameState.startTime) / 1000);
  
  // Save to backend
  try {
    const response = await fetch('/matches/save-solo-run/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        wallsSurvived: gameState.wallsSurvived,
        wallsHit: gameState.wallsHit,
        survivalTime: survivalTime,
        finalGridState: {
          playerPos: gameState.player,
          walls: gameState.walls,
          countdownWalls: gameState.countdownWalls
        }
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      showGameOver(data);
    } else {
      alert('Error saving game: ' + data.error);
    }
  } catch (error) {
    alert('Error: ' + error.message);
  }
}

function showGameOver(data) {
  document.getElementById('finalWalls').textContent = data.wallsSurvived;
  document.getElementById('finalHits').textContent = gameState.wallsHit;
  document.getElementById('finalTime').textContent = 
    Math.floor((Date.now() - gameState.startTime) / 1000) + 's';
  document.getElementById('coinsEarned').textContent = '+' + data.coinsEarned.toFixed(0);
  document.getElementById('coinsLost').textContent = '-' + data.coinsLost.toFixed(0);
  
  const net = data.netCoins;
  const netEl = document.getElementById('netCoins');
  netEl.textContent = (net >= 0 ? '+' : '') + net.toFixed(0);
  netEl.style.color = net >= 0 ? '#10b981' : '#ef4444';
  
  document.getElementById('newBalance').textContent = data.newBalance.toFixed(0);
  
  document.getElementById('gameOver').style.display = 'block';
}

function getCookie(name) {
  let value = '; ' + document.cookie;
  let parts = value.split('; ' + name + '=');
  if (parts.length === 2) return parts.pop().split(';').shift();
}

function startGame() {
  gameStarted = true;
  document.getElementById('startScreen').style.display = 'none';
  document.getElementById('gameCanvas').style.display = 'block';
  document.getElementById('controls').style.display = 'block';
  document.getElementById('hud').style.display = 'block';
  initGame();
}

// Don't auto-start - wait for button click
// initGame();