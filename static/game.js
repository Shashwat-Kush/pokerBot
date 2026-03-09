/* ============================================================
   game.js — Poker Bot Frontend Logic
   Talks to Flask API, renders cards, updates UI, draws graph
   ============================================================ */

'use strict';

// ── DOM refs ─────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const els = {
  // Cards
  playerCards  : $('player-cards'),
  botCards     : $('bot-cards'),
  boardCards   : $('board-cards'),

  // Chips & pot
  playerChips  : $('player-chips'),
  botChips     : $('bot-chips'),
  potAmount    : $('pot-amount'),
  playerBet    : $('player-bet-amount'),
  botBet       : $('bot-bet-amount'),
  playerBadge  : $('player-bet-badge'),
  botBadge     : $('bot-bet-badge'),

  // Info
  streetBadge  : $('street-badge'),
  blindsBadge  : $('blinds-badge'),
  messageBar   : $('message-bar'),

  // Action panel
  btnNewHand   : $('btn-new-hand'),
  bettingActions: $('betting-actions'),
  btnFold      : $('btn-fold'),
  btnCall      : $('btn-call'),
  callAmount   : $('call-amount'),
  btnRaise     : $('btn-raise'),
  btnAllin     : $('btn-allin'),
  raiseInput   : $('raise-input'),

  // Result overlay
  resultOverlay: $('result-overlay'),
  resultIcon   : $('result-icon'),
  resultTitle  : $('result-title'),
  resultHands  : $('result-hands'),
  btnResultNew : $('btn-result-new'),

  // Game Over overlay
  gameoverOverlay  : $('gameover-overlay'),
  gameoverIcon     : $('gameover-icon'),
  gameoverTitle    : $('gameover-title'),
  gameoverSubtitle : $('gameover-subtitle'),
  gameoverStats    : $('gameover-stats'),
  btnPlayAgain     : $('btn-play-again'),

  // Stats
  statHands    : $('stat-hands'),
  statWinrate  : $('stat-winrate'),
  statRecord   : $('stat-record'),
  statStreak   : $('stat-streak'),
  handHistory  : $('hand-history'),
  graphEmpty   : $('graph-empty'),
  chipGraph    : $('chipGraph'),

  // Reset
  btnResetStats: $('btn-reset-stats'),
};

// ── State ────────────────────────────────────────────────────
let gameState  = null;
let chipHistory = [];   // [{hand, chips}]


// ── Card rendering ───────────────────────────────────────────

const SUIT_SYMBOLS = { s: '♠', h: '♥', d: '♦', c: '♣' };
const RED_SUITS    = new Set(['h', 'd']);

/**
 * Parse a short card string like "A♠" or "??" into parts.
 * Returns null for hidden cards.
 */
function parseCard(short) {
  if (short === '??') return null;
  // short = rank + suit_symbol, e.g. "A♠", "T♥", "10♦"
  // Suit is always the last character
  const suit_sym = short.slice(-1);
  const rank     = short.slice(0, -1);
  // Find suit code from symbol
  const suit = Object.keys(SUIT_SYMBOLS).find(k => SUIT_SYMBOLS[k] === suit_sym) || '?';
  return { rank, suit, suit_sym };
}

/**
 * Build a card DOM element.
 * @param {string} short - e.g. "A♠" or "??"
 * @param {number} delay - animation delay in ms
 */
function buildCard(short, delay = 0) {
  const el = document.createElement('div');
  el.classList.add('card');

  const parsed = parseCard(short);
  if (!parsed) {
    el.classList.add('card-back');
    return el;
  }

  const { rank, suit, suit_sym } = parsed;
  const colorClass = RED_SUITS.has(suit) ? 'card-red' : 'card-black';

  el.classList.add('card-face', colorClass);
  el.style.animationDelay = `${delay}ms`;
  el.innerHTML = `
    <div>
      <div class="card-rank">${rank}</div>
      <div class="card-suit-sm">${suit_sym}</div>
    </div>
    <div class="card-suit-lg">${suit_sym}</div>
    <div>
      <div class="card-suit-sm" style="transform:rotate(180deg)">${suit_sym}</div>
      <div class="card-rank"   style="transform:rotate(180deg)">${rank}</div>
    </div>
  `;
  return el;
}

/**
 * Render a list of card strings into a container element.
 */
function renderCards(container, cards, startDelay = 0) {
  container.innerHTML = '';
  cards.forEach((c, i) => {
    container.appendChild(buildCard(c, startDelay + i * 80));
  });
}


// ── State renderer ───────────────────────────────────────────

/**
 * Full UI update from a game state object returned by the API.
 */
function applyState(state, message = '') {
  gameState = state;

  // Cards
  renderCards(els.playerCards, state.player_hole, 0);
  renderCards(els.botCards,    state.bot_hole,    80);
  renderCards(els.boardCards,  state.board,       160);

  // Chips
  els.playerChips.textContent = state.player_chips;
  els.botChips.textContent    = state.bot_chips;
  els.potAmount.textContent   = state.pot;

  // Bet badges
  if (state.player_bet > 0) {
    els.playerBadge.style.display = 'block';
    els.playerBet.textContent     = state.player_bet;
  } else {
    els.playerBadge.style.display = 'none';
  }
  if (state.bot_bet > 0) {
    els.botBadge.style.display = 'block';
    els.botBet.textContent     = state.bot_bet;
  } else {
    els.botBadge.style.display = 'none';
  }

  // Street
  els.streetBadge.textContent = state.street === 'PREFLOP' ? 'Pre-Flop'
    : state.street === 'FLOP'     ? 'Flop'
    : state.street === 'TURN'     ? 'Turn'
    : state.street === 'RIVER'    ? 'River'
    : state.street === 'SHOWDOWN' ? 'Showdown'
    : '—';

  // Message
  if (message) setMessage(message);

  // Action buttons
  const handOver = !state.hand_active;
  if (handOver) {
    showEndState(state);
  } else if (state.player_turn) {
    showBettingActions(state);
  } else {
    // Bot's turn — disable everything, show waiting message
    hideBettingActions();
    setMessage('Bot is thinking…');
  }
}

function showBettingActions(state) {
  els.btnNewHand.style.display     = 'none';
  els.bettingActions.style.display = 'flex';

  // Call / Check label
  if (state.amount_to_call === 0) {
    els.btnCall.textContent = 'Check';
  } else {
    els.btnCall.innerHTML = `Call <span id="call-amount">${state.amount_to_call}</span>`;
  }

  // All In button — show stack size, hide if already all-in
  const allInAmount = state.player_chips + state.player_bet;
  if (state.player_chips > 0) {
    els.btnAllin.style.display   = 'inline-block';
    els.btnAllin.textContent     = `All In (${state.player_chips})`;
    els.btnAllin.dataset.amount  = allInAmount;
  } else {
    els.btnAllin.style.display = 'none';
  }

  // Raise input min
  const minRaise = state.current_bet + state.min_raise;
  els.raiseInput.min   = minRaise;
  els.raiseInput.value = minRaise;
}

function hideBettingActions() {
  els.bettingActions.style.display = 'none';
  els.btnNewHand.style.display     = 'inline-block';
}

function showEndState(state) {
  hideBettingActions();

  // Check for game over — either player bust
  if (state.player_chips === 0 || state.bot_chips === 0) {
    setTimeout(() => showGameOver(state), 600);
    return;
  }

  // Normal hand end overlay
  setTimeout(() => {
    const winner = state.winner;

    if (winner === 'player') {
      els.resultIcon.textContent  = '🏆';
      els.resultTitle.textContent = 'You Win!';
      els.resultTitle.style.color = 'var(--win-green)';
    } else if (winner === 'bot') {
      els.resultIcon.textContent  = '🤖';
      els.resultTitle.textContent = 'Bot Wins';
      els.resultTitle.style.color = 'var(--loss-red)';
    } else {
      els.resultIcon.textContent  = '🤝';
      els.resultTitle.textContent = 'Split Pot';
      els.resultTitle.style.color = 'var(--gold)';
    }

    const ph = state.player_hand_name
      ? `You: ${state.player_hand_name.split('(')[0].trim()}`
      : (winner === 'bot' ? 'You folded' : '');
    const bh = state.bot_hand_name
      ? `Bot: ${state.bot_hand_name.split('(')[0].trim()}`
      : (winner === 'player' ? 'Bot folded' : '');

    els.resultHands.innerHTML = [ph, bh].filter(Boolean).join('<br>');
    els.resultOverlay.style.display = 'flex';

    loadStats();
  }, 400);
}

function showGameOver(state) {
  const playerWon = state.bot_chips === 0;

  els.gameoverIcon.textContent     = playerWon ? '🏆' : '💀';
  els.gameoverTitle.textContent    = playerWon ? 'You Win!' : 'Game Over';
  els.gameoverTitle.style.color    = playerWon ? 'var(--win-green)' : 'var(--loss-red)';
  els.gameoverSubtitle.textContent = playerWon
    ? 'You busted the bot!'
    : 'You ran out of chips.';

  // Pull final stats
  fetch('/stats').then(r => r.json()).then(data => {
    const s = data.summary;
    els.gameoverStats.innerHTML = `
      <div class="gameover-stat-row">
        <span>Hands played</span><span>${s.total_hands}</span>
      </div>
      <div class="gameover-stat-row">
        <span>Win rate</span><span>${s.win_rate}%</span>
      </div>
      <div class="gameover-stat-row">
        <span>Record</span><span>${s.player_wins}W – ${s.bot_wins}L</span>
      </div>
    `;
  });

  els.gameoverOverlay.style.display = 'flex';
}


// ── Message helper ───────────────────────────────────────────

function setMessage(msg) {
  els.messageBar.textContent = msg;
}


// ── API calls ────────────────────────────────────────────────

async function apiPost(endpoint, body = {}) {
  const res = await fetch(endpoint, {
    method : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body   : JSON.stringify(body),
  });
  return res.json();
}

async function newHand() {
  els.resultOverlay.style.display = 'none';
  els.btnNewHand.disabled         = true;
  setMessage('Dealing…');

  try {
    const state = await apiPost('/new_hand');
    applyState(state, state.message || 'New hand dealt.');
  } catch (e) {
    setMessage('Error starting hand. Is the server running?');
  } finally {
    els.btnNewHand.disabled = false;
  }
}

async function sendAction(action, amount = 0) {
  // Disable buttons while waiting
  setButtonsDisabled(true);

  try {
    const state = await apiPost('/action', { action, amount });
    applyState(state, state.message || '');
  } catch (e) {
    setMessage('Server error. Try again.');
  } finally {
    setButtonsDisabled(false);
  }
}

function setButtonsDisabled(disabled) {
  [els.btnFold, els.btnCall, els.btnRaise, els.btnAllin, els.raiseInput].forEach(el => {
    el.disabled = disabled;
  });
}


// ── Stats ────────────────────────────────────────────────────

async function loadStats() {
  try {
    const data = await fetch('/stats').then(r => r.json());
    renderStats(data.summary, data.history);
  } catch (e) {
    console.warn('Could not load stats:', e);
  }
}

function renderStats(summary, history) {
  // Summary cards
  els.statHands.textContent   = summary.total_hands;
  els.statWinrate.textContent = summary.total_hands
    ? `${summary.win_rate}%` : '—';
  els.statRecord.textContent  = `${summary.player_wins}W ${summary.bot_wins}L`;
  els.statStreak.textContent  = summary.current_streak;

  // Chip history graph
  chipHistory = summary.chip_history || [];
  drawChipGraph();

  // Hand history list
  renderHistory(history);
}

function renderHistory(history) {
  if (!history || history.length === 0) {
    els.handHistory.innerHTML = '<div class="history-empty">No hands yet</div>';
    return;
  }

  // Show most recent first
  const rows = [...history].reverse().map(h => {
    const resultClass = h.winner === 'player' ? 'win'
      : h.winner === 'bot' ? 'loss' : 'tie';
    const resultText  = h.winner === 'player' ? 'WIN'
      : h.winner === 'bot' ? 'loss' : 'tie';
    const handName = h.player_hand_name || (h.ended_by === 'fold' ? 'folded' : '—');

    return `
      <div class="history-row">
        <span class="history-num">#${h.hand_number}</span>
        <span class="history-result ${resultClass}">${resultText}</span>
        <span class="history-hand">${handName}</span>
        <span class="history-pot">${h.pot}</span>
      </div>
    `;
  });

  els.handHistory.innerHTML = rows.join('');
}


// ── Chip graph ───────────────────────────────────────────────

function drawChipGraph() {
  const canvas = els.chipGraph;
  const ctx    = canvas.getContext('2d');
  const W      = canvas.width;
  const H      = canvas.height;

  ctx.clearRect(0, 0, W, H);

  if (chipHistory.length < 2) {
    els.graphEmpty.style.display = 'block';
    return;
  }
  els.graphEmpty.style.display = 'none';

  const chips  = chipHistory.map(h => h.chips);
  const minVal = Math.min(...chips);
  const maxVal = Math.max(...chips);
  const range  = maxVal - minVal || 1;

  const pad  = { top: 8, bottom: 8, left: 6, right: 6 };
  const gW   = W - pad.left - pad.right;
  const gH   = H - pad.top  - pad.bottom;

  const xPos = i => pad.left + (i / (chips.length - 1)) * gW;
  const yPos = v => pad.top  + (1 - (v - minVal) / range) * gH;

  // Baseline (1000 starting chips)
  const baseY = yPos(1000);
  ctx.beginPath();
  ctx.setLineDash([3, 4]);
  ctx.strokeStyle = 'rgba(255,255,255,0.1)';
  ctx.lineWidth   = 1;
  ctx.moveTo(pad.left, baseY);
  ctx.lineTo(W - pad.right, baseY);
  ctx.stroke();
  ctx.setLineDash([]);

  // Gradient fill under line
  const gradient = ctx.createLinearGradient(0, pad.top, 0, H);
  gradient.addColorStop(0,   'rgba(201,168,76,0.35)');
  gradient.addColorStop(1,   'rgba(201,168,76,0.02)');

  ctx.beginPath();
  ctx.moveTo(xPos(0), yPos(chips[0]));
  chips.forEach((v, i) => { if (i > 0) ctx.lineTo(xPos(i), yPos(v)); });
  ctx.lineTo(xPos(chips.length - 1), H);
  ctx.lineTo(xPos(0), H);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.moveTo(xPos(0), yPos(chips[0]));
  chips.forEach((v, i) => { if (i > 0) ctx.lineTo(xPos(i), yPos(v)); });
  ctx.strokeStyle = 'var(--gold)';
  ctx.lineWidth   = 2;
  ctx.lineJoin    = 'round';
  ctx.stroke();

  // Dots at each point
  chips.forEach((v, i) => {
    ctx.beginPath();
    ctx.arc(xPos(i), yPos(v), 2.5, 0, Math.PI * 2);
    ctx.fillStyle = 'var(--gold-light)';
    ctx.fill();
  });

  // Last value label
  const lastX = xPos(chips.length - 1);
  const lastY = yPos(chips[chips.length - 1]);
  ctx.font      = '10px DM Mono, monospace';
  ctx.fillStyle = 'rgba(201,168,76,0.8)';
  ctx.textAlign = 'right';
  ctx.fillText(chips[chips.length - 1], lastX - 4, lastY - 6);
}


// ── Event listeners ──────────────────────────────────────────

els.btnNewHand.addEventListener('click', newHand);
els.btnResultNew.addEventListener('click', newHand);

els.btnFold.addEventListener('click', () => sendAction('fold'));

els.btnCall.addEventListener('click', () => {
  const action = gameState?.amount_to_call === 0 ? 'check' : 'call';
  sendAction(action);
});

els.btnRaise.addEventListener('click', () => {
  const amount = parseInt(els.raiseInput.value, 10);
  if (isNaN(amount) || amount <= 0) {
    setMessage('Enter a valid raise amount.');
    return;
  }
  sendAction('raise', amount);
});

els.btnAllin.addEventListener('click', () => {
  const amount = parseInt(els.btnAllin.dataset.amount, 10);
  sendAction('raise', amount);
});

// Allow Enter key in raise input
els.raiseInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') els.btnRaise.click();
});

els.btnResetStats.addEventListener('click', async () => {
  if (!confirm('Reset all stats? This cannot be undone.')) return;
  await apiPost('/reset_stats');
  chipHistory = [];
  drawChipGraph();
  loadStats();
});

els.btnPlayAgain.addEventListener('click', async () => {
  // Reset both chip stacks on the server then start fresh
  els.gameoverOverlay.style.display = 'none';
  await apiPost('/reset_game');
  chipHistory = [];
  drawChipGraph();
  await loadStats();
  newHand();
});


// ── Init ─────────────────────────────────────────────────────

loadStats();


// ── Developer Panel ──────────────────────────────────────────

const devEls = {
  panel      : $('dev-panel'),
  btnToggle  : $('btn-dev-toggle'),
  btnClose   : $('btn-close-dev'),
  botCards   : $('dev-bot-cards'),
  equity     : $('dev-equity'),
  equityBar  : $('dev-equity-bar'),
  odds       : $('dev-odds'),
  oddsBar    : $('dev-odds-bar'),
  ev         : $('dev-ev'),
  evBar      : $('dev-ev-bar'),
  decision   : $('dev-decision'),
  reasoning  : $('dev-reasoning'),
  log        : $('dev-log'),
  handNum    : $('dev-hand-num'),
};

// Toggle open/close
devEls.btnToggle.addEventListener('click', () => {
  devEls.panel.classList.toggle('open');
});
devEls.btnClose.addEventListener('click', () => {
  devEls.panel.classList.remove('open');
});

// Track last street+turn we fetched equity for — prevents fetch loop
let _lastEquityFetch = null;

/**
 * Update the dev panel from the state returned by the API.
 * Called inside applyState() on every state update.
 */
function applyDebug(state) {
  // ── Bot hole cards — use bot_hole_actual (always real) ────
  const actual = state.bot_hole_actual;
  if (actual && actual.length === 2 && actual[0] !== '??') {
    renderCards(devEls.botCards, actual, 0);
  }

  // ── Live equity fetch — only once per street per turn ─────
  // Key: street + hand_active prevents re-fetching on same state
  const fetchKey = `${state.street}-${state.pot}-${state.current_bet}`;
  if (state.hand_active && state.player_turn &&
      actual && actual[0] !== '??' &&
      fetchKey !== _lastEquityFetch) {
    _lastEquityFetch = fetchKey;
    fetchLiveEquity(actual, state.board, state.pot, state.current_bet, state.bot_bet);
  }

  // ── Last bot decision stats (after bot acts) ──────────────
  const d = state.debug;
  if (d && Object.keys(d).length > 0) {
    renderDecisionStats(d);
  }

  // ── Action log ────────────────────────────────────────────
  const log = state.action_log || [];
  if (log.length === 0) {
    devEls.log.innerHTML = '<div class="dev-log-empty">No decisions yet</div>';
    return;
  }

  devEls.log.innerHTML = log.map((entry) => {
    const cls      = decisionClass(entry.decision);
    const evStr    = (entry.ev >= 0 ? '+' : '') + entry.ev + '%';
    const oddsStr  = entry.pot_odds === 0
      ? 'No bet (free)'
      : `Odds ${entry.pot_odds}%`;
    return `
      <div class="dev-log-entry ${cls}">
        <div class="dev-log-top">
          <span class="dev-log-street">${entry.street || ''}</span>
          <span class="dev-log-decision">${entry.decision || '—'}</span>
          <span class="dev-log-ev">${evStr}</span>
        </div>
        <div class="dev-log-eq">Eq ${entry.equity}%  ·  ${oddsStr}</div>
        <div class="dev-log-reason">${entry.reasoning || ''}</div>
      </div>
    `;
  }).reverse().join('');
}

/** Render equity/odds/ev bars and decision badge from a debug dict. */
function renderDecisionStats(d) {
  const equity = d.equity   ?? 0;
  const odds   = d.pot_odds ?? 0;
  const ev     = d.ev       ?? 0;

  devEls.equity.textContent         = `${equity}%`;
  devEls.equityBar.style.width      = `${Math.min(equity, 100)}%`;
  devEls.equityBar.style.background = equity >= 52 ? 'var(--win-green)' : 'var(--loss-red)';

  devEls.odds.textContent           = odds === 0 ? 'No bet' : `${odds}%`;
  devEls.oddsBar.style.width        = `${Math.min(odds, 100)}%`;

  const evAbs = Math.abs(ev);
  devEls.ev.textContent             = `${ev > 0 ? '+' : ''}${ev}%`;
  devEls.evBar.style.width          = `${Math.min(evAbs, 50)}%`;
  devEls.evBar.style.background     = ev >= 0 ? 'var(--win-green)' : 'var(--loss-red)';

  devEls.decision.textContent  = d.decision || '—';
  devEls.decision.className    = 'dev-decision ' + decisionClass(d.decision);
  devEls.reasoning.textContent = d.reasoning || '—';
}

/** Fetch live equity for the bot's current hand from the server. */
async function fetchLiveEquity(botCards, board, pot, currentBet, botBet) {
  try {
    const res = await fetch('/debug/equity', {
      method : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body   : JSON.stringify({
        bot_cards   : botCards,
        board       : board,
        pot         : pot,
        current_bet : currentBet,
        bot_bet     : botBet,
      }),
    });
    const data = await res.json();
    if (data && data.equity !== undefined) {
      renderDecisionStats(data);
    }
  } catch (e) {
    console.warn('Live equity fetch failed:', e);
  }
}

function decisionClass(decision) {
  if (!decision) return '';
  const d = decision.toUpperCase();
  if (d.includes('FOLD'))          return 'decision-fold';
  if (d.includes('BLUFF'))         return 'decision-bluff';
  if (d.includes('RAISE STRONG'))  return 'decision-raise-strong';
  if (d.includes('RAISE MEDIUM'))  return 'decision-raise-medium';
  if (d.includes('RAISE'))         return 'decision-raise-medium';
  if (d.includes('CALL') || d.includes('CHECK')) return 'decision-call';
  return '';
}

// Hook into applyState — patch it to also call applyDebug
const _origApplyState = applyState;
// eslint-disable-next-line no-global-assign
applyState = function(state, message = '') {
  _origApplyState(state, message);
  applyDebug(state);
};