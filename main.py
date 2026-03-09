"""
main.py - Main Game Loop
==========================
The entry point. Wires together the engine, bot, and UI into a playable game.

Run with:
    python main.py

Dependencies:
    pip install treys
"""

import time
from engine import GameEngine, GameState, Street, Action, Winner
from bot    import get_action
from stats  import StatsTracker
import ui


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

STARTING_CHIPS = 1000
BIG_BLIND      = 20
BOT_DELAY      = 0.8    # seconds to pause after bot acts (feels more natural)


# ---------------------------------------------------------------------------
# Action message builder
# ---------------------------------------------------------------------------

def _action_msg(who: str, action: Action, amount: int, state: GameState) -> str:
    """Build a human-readable description of the last action."""
    name = "You" if who == "player" else "Bot"
    if action == Action.FOLD:
        return f"{name} folded."
    elif action == Action.CHECK:
        return f"{name} checked."
    elif action == Action.CALL:
        to_call = state.current_bet - (state.player_bet if who == "player" else state.bot_bet)
        return f"{name} called {to_call}."
    elif action == Action.RAISE:
        return f"{name} raised to {amount}."
    return ""


# ---------------------------------------------------------------------------
# Single hand loop
# ---------------------------------------------------------------------------

def play_hand(engine: GameEngine, tracker: StatsTracker, hand_number: int) -> GameState:
    """
    Play one complete hand from deal to resolution.

    Args:
        engine:      The GameEngine instance (carries chip stacks between hands).
        tracker:     StatsTracker instance to record the result.
        hand_number: Used to alternate the dealer button.

    Returns:
        The final GameState after the hand ends.
    """
    player_is_dealer = (hand_number % 2 == 1)
    state = engine.start_hand(player_is_dealer=player_is_dealer)

    dealer_label = "You" if player_is_dealer else "Bot"
    last_msg = f"Hand #{hand_number}  |  Dealer: {dealer_label}  |  Blinds: {engine.small_blind}/{engine.big_blind}"

    while engine.hand_active:
        ui.render_table(state, last_action_msg=last_msg)

        if state.player_turn:
            # ── Player's turn ──
            action, amount = ui.get_player_action(state)
            prev_state     = state
            state          = engine.apply_action(action, amount)
            last_msg       = _action_msg("player", action, amount, prev_state)

        else:
            # ── Bot's turn ──
            print(f"\n  Bot is thinking...")
            time.sleep(BOT_DELAY)

            action, amount = get_action(state)
            prev_state     = state
            state          = engine.apply_action(action, amount)
            last_msg       = _action_msg("bot", action, amount, prev_state)

    # ── Hand over — render final screen ──
    if state.street == Street.SHOWDOWN:
        ui.render_showdown(state)
        tracker.record_hand(state, hand_number, folder=None)
    else:
        # Someone folded
        folder = "player" if state.winner == Winner.BOT else "bot"
        ui.render_hand_over_fold(state, folder)
        tracker.record_hand(state, hand_number, folder=folder)

    # ── Show stats after every hand ──
    summary = tracker.summary()
    ui.render_stats_summary(summary)
    ui.render_hand_history(tracker.last_n_hands(5))
    ui.render_chip_graph(summary['chip_history'])

    return state


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ui.clear()
    ui.print_header()
    print(f"""
  Welcome to Heads-Up Poker Bot!

  Rules:
    ● Texas Hold'em, heads-up (you vs the bot)
    ● Starting chips : {STARTING_CHIPS} each
    ● Blinds         : {BIG_BLIND // 2} / {BIG_BLIND}
    ● Dealer alternates each hand

  Controls:
    f          → Fold
    c          → Call / Check
    r <amount> → Raise  (e.g. "r 100")
""")
    ui.divider()
    input("  Press Enter to start...\n")

    engine      = GameEngine(starting_chips=STARTING_CHIPS, big_blind=BIG_BLIND)
    tracker     = StatsTracker()
    hand_number = 0

    while True:
        # ── Check for game over before starting a hand ──
        if engine.player_chips <= 0:
            ui.clear()
            ui.print_header()
            print("\n  You're out of chips. Game over — Bot wins!\n")
            ui.divider()
            break

        if engine.bot_chips <= 0:
            ui.clear()
            ui.print_header()
            print("\n  Bot is out of chips. You win the game! 🏆\n")
            ui.divider()
            break

        hand_number += 1
        final_state = play_hand(engine, tracker, hand_number)

        # ── Ask to continue ──
        if not ui.ask_play_again():
            ui.clear()
            ui.print_header()
            print(f"\n  Thanks for playing!")
            print(f"  Final chips — You: {engine.player_chips}  |  Bot: {engine.bot_chips}")
            final = "ahead" if engine.player_chips > engine.bot_chips else \
                    "behind" if engine.player_chips < engine.bot_chips else "even"
            print(f"  You finished {final}.\n")
            ui.divider()
            break

    print()


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()