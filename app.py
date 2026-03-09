"""
app.py - Flask Web Server
==========================
Serves the poker web UI and exposes a JSON API for game actions.
Holds game state in memory between requests.

Run with:
    python app.py

Then open: http://localhost:5000

API endpoints:
    GET  /              → serves index.html
    POST /new_hand      → start a new hand, returns state JSON
    POST /action        → apply player action, auto-plays bot, returns state JSON
    GET  /stats         → returns stats + hand history JSON
    POST /reset_stats   → wipes stats.json
"""

import time
from flask   import Flask, render_template, request, jsonify
from engine  import GameEngine, GameState, Street, Action, Winner
import bot as bot_module
from bot     import get_action
from stats   import StatsTracker


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app    = Flask(__name__)
engine  = GameEngine(starting_chips=1000, big_blind=20)
tracker = StatsTracker()

# Track hand number for dealer alternation
_hand_number  = 0
_action_log   = []       # accumulated decision log for current hand
BOT_THINK_DELAY = 0.6


# ---------------------------------------------------------------------------
# State serializer
# ---------------------------------------------------------------------------

def _serialize_state(state: GameState, message: str = "") -> dict:
    """
    Convert a GameState into a JSON-serializable dict for the browser.
    Bot hole cards are hidden unless it's showdown.
    """
    reveal_bot = state.street in (Street.SHOWDOWN, Street.HAND_OVER)

    return {
        # Cards
        "player_hole"     : [c.short() for c in state.player_hole],
        "bot_hole"        : [c.short() for c in state.bot_hole] if reveal_bot else ["??", "??"],
        "bot_hole_actual" : [c.short() for c in state.bot_hole],   # always for dev panel
        "board"           : [c.short() for c in state.board],

        # Money
        "pot"          : state.pot,
        "player_chips" : state.player_chips,
        "bot_chips"    : state.bot_chips,
        "player_bet"   : state.player_bet,
        "bot_bet"      : state.bot_bet,
        "big_blind"    : state.big_blind,
        "current_bet"  : state.current_bet,
        "min_raise"    : state.min_raise,
        "amount_to_call": state.amount_to_call(),

        # Street / turn
        "street"       : state.street.name,
        "player_turn"  : state.player_turn,
        "hand_active"  : engine.hand_active,

        # End of hand
        "winner"           : state.winner.value if state.winner else None,
        "player_hand_name" : state.player_hand_name,
        "bot_hand_name"    : state.bot_hand_name,

        # UI message
        "message"      : message,

        # Developer panel
        "debug"        : bot_module.last_debug,
        "action_log"   : list(_action_log),
    }


def _action_message(who: str, action: Action, amount: int, prev_state: GameState) -> str:
    """Build a human-readable action description."""
    name = "You" if who == "player" else "Bot"
    if action == Action.FOLD:
        return f"{name} folded."
    elif action == Action.CHECK:
        return f"{name} checked."
    elif action == Action.CALL:
        to_call = prev_state.current_bet - (
            prev_state.player_bet if who == "player" else prev_state.bot_bet
        )
        return f"{name} called {to_call}."
    elif action == Action.RAISE:
        return f"{name} raised to {amount}."
    return ""


# ---------------------------------------------------------------------------
# Bot auto-play helper
# ---------------------------------------------------------------------------

def _play_bot_turns(state: GameState) -> tuple[GameState, str]:
    """
    Keep playing bot turns until it's the player's turn or hand ends.
    Appends each decision to _action_log.
    Guard: max 6 bot actions per call to prevent infinite loops.
    """
    global _action_log
    message  = ""
    max_turns = 6   # safety cap — never more than 6 consecutive bot actions

    while engine.hand_active and not state.player_turn and max_turns > 0:
        max_turns -= 1
        time.sleep(BOT_THINK_DELAY)
        action, amount = get_action(state)
        # Snapshot debug info immediately after decision
        if bot_module.last_debug:
            entry = dict(bot_module.last_debug)
            entry["street"] = state.street.name
            _action_log.append(entry)
            _action_log[:] = _action_log[-8:]   # keep last 8 only
        prev_state = state
        state      = engine.apply_action(action, amount)
        message    = _action_message("bot", action, amount, prev_state)

    return state, message


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main game page."""
    return render_template("index.html")


@app.route("/new_hand", methods=["POST"])
def new_hand():
    global _hand_number, _action_log
    _hand_number += 1
    _action_log   = []   # reset log for new hand
    bot_module.last_debug = {}

    player_is_dealer = (_hand_number % 2 == 1)
    state = engine.start_hand(player_is_dealer=player_is_dealer)

    dealer_label = "You" if player_is_dealer else "Bot"
    message = f"Hand #{_hand_number} — Dealer: {dealer_label}"

    # If bot acts first pre-flop, play its turn
    if not state.player_turn:
        state, bot_msg = _play_bot_turns(state)
        if bot_msg:
            message += f" | {bot_msg}"

    return jsonify(_serialize_state(state, message))


@app.route("/action", methods=["POST"])
def action():
    """
    Apply a player action and auto-play the bot's response.

    Request JSON:
        { "action": "fold" | "call" | "check" | "raise", "amount": <int> }

    Returns updated state JSON.
    """
    if not engine.hand_active:
        return jsonify({"error": "No active hand. Start a new hand first."}), 400

    data       = request.get_json()
    action_str = data.get("action", "").lower()
    amount     = int(data.get("amount", 0))

    # Map string → Action enum
    action_map = {
        "fold"  : Action.FOLD,
        "call"  : Action.CALL,
        "check" : Action.CHECK,
        "raise" : Action.RAISE,
    }

    if action_str not in action_map:
        return jsonify({"error": f"Unknown action: {action_str}"}), 400

    player_action = action_map[action_str]
    prev_state    = engine._snapshot()   # capture before applying
    state         = engine.apply_action(player_action, amount)
    message       = _action_message("player", player_action, amount, prev_state)

    # Auto-play bot turns
    if engine.hand_active and not state.player_turn:
        state, bot_msg = _play_bot_turns(state)
        if bot_msg:
            message += f" | {bot_msg}"

    # Record hand if it just ended
    if not engine.hand_active:
        folder = None
        if state.street == Street.HAND_OVER:
            folder = "player" if state.winner == Winner.BOT else "bot"
        tracker.record_hand(state, _hand_number, folder=folder)

    return jsonify(_serialize_state(state, message))


@app.route("/stats")
def stats():
    """Return stats summary and last 10 hands as JSON."""
    summary = tracker.summary()
    history = [
        {
            "hand_number"      : h.hand_number,
            "winner"           : h.winner,
            "ended_by"         : h.ended_by,
            "pot"              : h.pot,
            "player_hand_name" : h.player_hand_name.split('(')[0].strip(),
            "bot_hand_name"    : h.bot_hand_name.split('(')[0].strip(),
            "player_chips_after": h.player_chips_after,
            "timestamp"        : h.timestamp,
        }
        for h in tracker.last_n_hands(10)
    ]
    return jsonify({"summary": summary, "history": history})


@app.route("/reset_stats", methods=["POST"])
def reset_stats():
    """Wipe all stats history."""
    tracker.reset()
    return jsonify({"status": "ok"})


@app.route("/debug/equity", methods=["POST"])
def debug_equity():
    """
    Dev panel live equity endpoint.
    Runs Monte Carlo on the bot's current hand and returns stats.
    Called on every player turn so the dev panel stays live.
    """
    from monte_carlo import estimate_equity, pot_odds as calc_pot_odds
    from deck import Card

    data      = request.get_json()
    bot_cards = data.get('bot_cards', [])
    board     = data.get('board', [])
    pot       = int(data.get('pot', 0))
    cur_bet   = int(data.get('current_bet', 0))
    bot_bet   = int(data.get('bot_bet', 0))

    def parse_card(s):
        if s in ('??', ''): return None
        suit_map = {'♠':'s','♥':'h','♦':'d','♣':'c'}
        suit = suit_map.get(s[-1], 's')
        rank = s[:-1]
        return Card(rank, suit)

    hole        = [c for c in (parse_card(s) for s in bot_cards)  if c]
    board_cards = [c for c in (parse_card(s) for s in board)      if c]

    if len(hole) < 2:
        return jsonify({'error': 'not enough cards'}), 400

    equity  = estimate_equity(hole, board_cards, simulations=500)
    to_call = max(cur_bet - bot_bet, 0)
    p_odds  = calc_pot_odds(to_call, pot) if pot > 0 else 0.0
    ev      = round((equity - p_odds) * 100, 1)
    eq_pct  = round(equity * 100, 1)
    od_pct  = round(p_odds * 100, 1)

    if equity >= 0.65:
        decision  = 'RAISE STRONG'
        reasoning = f'Equity {eq_pct}% ≥ 65% threshold → would raise big.'
    elif equity >= 0.52:
        decision  = 'RAISE MEDIUM'
        reasoning = f'Equity {eq_pct}% ≥ 52% → would raise medium.'
    elif equity > p_odds:
        decision  = 'CALL (+EV)'
        reasoning = f'Equity {eq_pct}% > pot odds {od_pct}% → would call.'
    else:
        decision  = 'FOLD'
        reasoning = f'Equity {eq_pct}% < pot odds {od_pct}% → would fold.'

    return jsonify({
        'equity'   : eq_pct,
        'pot_odds' : od_pct,
        'ev'       : ev,
        'decision' : decision,
        'reasoning': reasoning,
    })


@app.route("/reset_game", methods=["POST"])
def reset_game():
    """Reset both chip stacks to starting amount for a fresh game."""
    engine.player_chips = 1000
    engine.bot_chips    = 1000
    tracker.reset()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("╔══════════════════════════════════╗")
    print("║   Poker Bot — Web UI             ║")
    print("║   http://localhost:5000          ║")
    print("╚══════════════════════════════════╝")
    app.run(debug=True, port=5000)