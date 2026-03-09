"""
bot.py - Level 2 Monte Carlo Bot
==================================
Makes decisions based on actual win probability (equity) vs pot odds.
Replaces the Level 1 rule-based hand category system entirely.

Decision framework:
  1. Estimate equity via Monte Carlo simulation
  2. Calculate pot odds from the current bet
  3. Compare equity vs pot odds to determine EV
  4. Raise if significantly ahead, call if marginal, fold if behind
  5. Bluff occasionally with small frequency to stay unpredictable

Key improvement over Level 1:
  - Bot can now be bluffed off strong-but-not-dominant hands
  - Raise sizing is proportional to actual equity, not fixed categories
  - Responds correctly to oversized bets (your big bluffs now work)
  - Performs consistently across all streets without special-case logic
"""

import random
from engine      import Action, GameState, Street
from monte_carlo import estimate_equity, pot_odds, has_positive_ev


# ---------------------------------------------------------------------------
# Tuning parameters
# ---------------------------------------------------------------------------

SIMULATIONS          = 1000   # Monte Carlo iterations per decision

# Equity thresholds
EQUITY_RAISE_STRONG  = 0.65   # raise big when equity >= 65%
EQUITY_RAISE_MEDIUM  = 0.52   # raise small when equity >= 52%

# Raise sizing (as a fraction of pot)
RAISE_STRONG         = 0.85   # 85% pot raise when very strong
RAISE_MEDIUM         = 0.50   # 50% pot raise when moderately strong
RAISE_BLUFF          = 0.60   # 60% pot raise when bluffing

# Bluff settings
BLUFF_CHANCE         = 0.10   # 10% chance to bluff regardless of equity
BLUFF_MAX_POT_ODDS   = 0.25   # only bluff when not facing a large bet


# ---------------------------------------------------------------------------
# Public interface  (same signature as Level 1 — main.py needs no changes)
# ---------------------------------------------------------------------------

def get_action(state: GameState) -> tuple[Action, int]:
    """
    Main entry point. Returns (Action, raise_amount).
    raise_amount is the TOTAL chips bot wants committed this street.
    It is 0 for FOLD / CHECK / CALL.
    """
    equity   = estimate_equity(state.bot_hole, state.board, SIMULATIONS)
    to_call  = state.amount_to_call()
    p_odds   = pot_odds(to_call, state.pot)
    actions  = _available(state)

    # ── Bluff branch ──────────────────────────────────────────────────────
    if (random.random() < BLUFF_CHANCE
            and Action.RAISE in actions
            and p_odds < BLUFF_MAX_POT_ODDS):
        amount = _raise_size(state, RAISE_BLUFF)
        return Action.RAISE, amount

    # ── Value branch ──────────────────────────────────────────────────────
    if equity >= EQUITY_RAISE_STRONG:
        if Action.RAISE in actions:
            return Action.RAISE, _raise_size(state, RAISE_STRONG)
        return _check_or_call(actions)

    elif equity >= EQUITY_RAISE_MEDIUM:
        if Action.RAISE in actions and p_odds < 0.40:
            return Action.RAISE, _raise_size(state, RAISE_MEDIUM)
        if has_positive_ev(equity, to_call, state.pot):
            return _check_or_call(actions)
        return Action.FOLD, 0

    else:
        if has_positive_ev(equity, to_call, state.pot):
            return _check_or_call(actions)
        if Action.CHECK in actions:
            return Action.CHECK, 0
        return Action.FOLD, 0


# ---------------------------------------------------------------------------
# Raise sizing
# ---------------------------------------------------------------------------

def _raise_size(state: GameState, fraction: float) -> int:
    """
    Calculate a pot-relative raise size.
    Returns total chips bot wants committed this street after the raise.
    Clamped to legal range [min_legal, bot_stack].
    """
    bet_amount = max(int(state.pot * fraction), state.big_blind)
    total      = state.bot_bet + bet_amount
    min_legal  = state.current_bet + state.min_raise
    max_legal  = state.bot_bet + state.bot_chips
    return max(min_legal, min(total, max_legal))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _available(state: GameState) -> list[Action]:
    actions = [Action.FOLD, Action.RAISE]
    if state.bot_bet == state.current_bet:
        actions.append(Action.CHECK)
    else:
        actions.append(Action.CALL)
    return actions


def _check_or_call(actions: list[Action]) -> tuple[Action, int]:
    if Action.CHECK in actions:
        return Action.CHECK, 0
    return Action.CALL, 0


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from engine import GameEngine

    print("=== bot.py (Level 2) self-test ===\n")

    engine = GameEngine(starting_chips=1000, big_blind=20)
    wins   = {'player': 0, 'bot': 0, 'tie': 0}

    for hand_num in range(10):
        state = engine.start_hand(player_is_dealer=(hand_num % 2 == 0))

        while engine.hand_active:
            if state.player_turn:
                to_call = state.amount_to_call()
                if to_call == 0:
                    state = engine.apply_action(Action.CHECK)
                else:
                    state = engine.apply_action(Action.CALL)
            else:
                action, amount = get_action(state)
                state = engine.apply_action(action, amount)

        result = state.winner.value
        wins[result] += 1

        hole_str  = f"{state.player_hole[0].short()}{state.player_hole[1].short()}"
        bot_str   = f"{state.bot_hole[0].short()}{state.bot_hole[1].short()}"
        board_str = ' '.join(c.short() for c in state.board) if state.board else "(folded)"

        print(
            f"Hand {hand_num+1:2d} | "
            f"Player: {hole_str} ({(state.player_hand_name or 'folded')[:15]:15s}) | "
            f"Bot: {bot_str} ({(state.bot_hand_name or 'folded')[:15]:15s}) | "
            f"Board: {board_str:20s} | "
            f"Winner: {result}"
        )

    print(f"\nAfter 10 hands → Player: {wins['player']}  Bot: {wins['bot']}  Ties: {wins['tie']}")
    print(f"Final chips    → Player: {engine.player_chips}  Bot: {engine.bot_chips}")
    print("\n✓ Level 2 bot self-test complete.")