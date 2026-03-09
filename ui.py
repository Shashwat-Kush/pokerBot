"""
ui.py - Command Line Interface
================================
Handles all display and player input. No game logic lives here.
Reads GameState and renders the table. Captures and validates player actions.

Controls:
    f         → Fold
    c         → Call / Check
    r <amount> → Raise to <amount> total chips this street
"""

import os
from engine import GameState, Street, Action, Winner


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def clear() -> None:
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def divider(char: str = "─", width: int = 50) -> None:
    print(char * width)


def print_header() -> None:
    divider("═")
    print("          ♠ ♥  HEADS-UP POKER BOT  ♦ ♣")
    divider("═")


# ---------------------------------------------------------------------------
# Table renderer
# ---------------------------------------------------------------------------

def render_table(state: GameState, last_action_msg: str = "") -> None:
    """
    Render the full table state to the terminal.

    Args:
        state:            Current GameState snapshot.
        last_action_msg:  Optional message describing the last action taken.
    """
    clear()
    print_header()

    # --- Bot section ---
    bot_cards = _format_bot_cards(state)
    print(f"\n  BOT  [{state.bot_chips} chips]")
    print(f"  Cards : {bot_cards}")
    print(f"  Bet   : {state.bot_bet}")

    # --- Board ---
    divider()
    board_str = "  ".join(c.short() for c in state.board) if state.board else "(no cards yet)"
    print(f"\n  Street : {state.street.name}")
    print(f"  Board  : {board_str}")
    print(f"  Pot    : {state.pot}")
    divider()

    # --- Player section ---
    player_cards = "  ".join(c.short() for c in state.player_hole)
    print(f"\n  YOU  [{state.player_chips} chips]")
    print(f"  Cards : {player_cards}")
    print(f"  Bet   : {state.player_bet}\n")

    # --- Last action message ---
    if last_action_msg:
        print(f"  ► {last_action_msg}")
        print()


def render_showdown(state: GameState) -> None:
    """
    Render the final showdown screen with both hands revealed.
    """
    clear()
    print_header()

    bot_cards   = "  ".join(c.short() for c in state.bot_hole)
    player_cards = "  ".join(c.short() for c in state.player_hole)
    board_str   = "  ".join(c.short() for c in state.board)

    print(f"\n  ── SHOWDOWN ──\n")
    print(f"  Board  : {board_str}\n")
    divider()

    print(f"\n  BOT    : {bot_cards}")
    print(f"           {state.bot_hand_name}")

    print(f"\n  YOU    : {player_cards}")
    print(f"           {state.player_hand_name}\n")

    divider()
    _print_winner(state.winner)
    divider()
    print(f"\n  Your chips : {state.player_chips}")
    print(f"  Bot chips  : {state.bot_chips}\n")


def render_hand_over_fold(state: GameState, folder: str) -> None:
    """
    Render the end screen when someone folded.

    Args:
        state:   Final GameState.
        folder:  'player' or 'bot'
    """
    clear()
    print_header()
    print()
    if folder == 'player':
        print("  You folded.")
        print(f"  Bot wins the pot.\n")
    else:
        print("  Bot folded.")
        print(f"  You win the pot!\n")

    divider()
    print(f"  Your chips : {state.player_chips}")
    print(f"  Bot chips  : {state.bot_chips}\n")


def render_chips(state: GameState) -> None:
    """Print a quick chip count summary between hands."""
    divider()
    print(f"  Your chips : {state.player_chips}")
    print(f"  Bot chips  : {state.bot_chips}")
    divider()


# ---------------------------------------------------------------------------
# Input handler
# ---------------------------------------------------------------------------

def get_player_action(state: GameState) -> tuple[Action, int]:
    """
    Display available actions and read the player's input.
    Loops until valid input is received.

    Returns:
        (Action, raise_amount) — raise_amount is 0 for non-raise actions.
    """
    valid = _build_valid_actions(state)
    prompt = _build_prompt(state, valid)

    while True:
        raw = input(prompt).strip().lower()
        result = _parse_input(raw, valid, state)
        if result is not None:
            return result
        print("  ✗ Invalid input. Try again.")


def ask_play_again() -> bool:
    """Ask the player if they want to play another hand."""
    divider()
    while True:
        raw = input("  Play another hand? (y / n) : ").strip().lower()
        if raw in ('y', 'yes'):
            return True
        if raw in ('n', 'no'):
            return False
        print("  ✗ Enter y or n.")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _format_bot_cards(state: GameState) -> str:
    """Show bot cards only at showdown, otherwise hide them."""
    if state.street == Street.SHOWDOWN:
        return "  ".join(c.short() for c in state.bot_hole)
    return "??  ??"


def _print_winner(winner: Winner) -> None:
    if winner == Winner.PLAYER:
        print("\n  🏆  YOU WIN THE HAND!\n")
    elif winner == Winner.BOT:
        print("\n  Bot wins the hand.\n")
    else:
        print("\n  Split pot — Tie!\n")


def _build_valid_actions(state: GameState) -> list[Action]:
    """
    Determine valid actions from the state.
    CHECK is available when player's bet already matches current bet.
    """
    actions = [Action.FOLD, Action.RAISE]
    if state.player_bet == state.current_bet:
        actions.append(Action.CHECK)
    else:
        actions.append(Action.CALL)
    return actions


def _build_prompt(state: GameState, valid: list[Action]) -> str:
    """Build the action prompt string shown to the player."""
    parts = []

    if Action.FOLD  in valid: parts.append("f=fold")
    if Action.CHECK in valid: parts.append("c=check")
    if Action.CALL  in valid:
        to_call = state.current_bet - state.player_bet
        parts.append(f"c=call({to_call})")
    if Action.RAISE in valid:
        parts.append(f"r <amount>=raise (min {state.min_raise + state.current_bet})")

    return f"  Action [{' | '.join(parts)}] : "


def _parse_input(
    raw: str,
    valid: list[Action],
    state: GameState
) -> tuple[Action, int] | None:
    """
    Parse raw input string into (Action, amount).
    Returns None if input is invalid.
    """
    if raw == 'f' and Action.FOLD in valid:
        return (Action.FOLD, 0)

    if raw == 'c':
        if Action.CHECK in valid:
            return (Action.CHECK, 0)
        if Action.CALL in valid:
            return (Action.CALL, 0)

    if raw.startswith('r') and Action.RAISE in valid:
        parts = raw.split()
        if len(parts) == 2 and parts[1].isdigit():
            amount = int(parts[1])
            min_total = state.current_bet + state.min_raise
            max_total = state.current_bet + state.player_chips  # can't raise more than stack
            if min_total <= amount <= max_total:
                return (Action.RAISE, amount)
            else:
                print(f"  ✗ Raise must be between {min_total} and {max_total}.")
                return None   # stay in loop, error already printed

    return None


# ---------------------------------------------------------------------------
# Stats display
# ---------------------------------------------------------------------------

def render_stats_summary(summary: dict) -> None:
    """
    Display a compact stats overview between hands.

    Args:
        summary: Dict returned by StatsTracker.summary()
    """
    divider("═")
    print("                  YOUR STATS")
    divider("═")

    if summary['total_hands'] == 0:
        print("\n  No hands played yet.\n")
        divider()
        return

    total   = summary['total_hands']
    wins    = summary['player_wins']
    losses  = summary['bot_wins']
    ties    = summary['ties']

    print(f"\n  Hands played   : {total}")
    print(f"  Record         : {wins}W  {losses}L  {ties}T")
    print(f"  Win rate       : {summary['win_rate']}%")
    print()
    print(f"  Biggest pot won  : {summary['biggest_pot_won']} chips")
    print(f"  Biggest pot lost : {summary['biggest_pot_lost']} chips")
    print()
    print(f"  Current streak : {summary['current_streak']} wins")
    print(f"  Best streak    : {summary['best_streak']} wins")

    # Most common hand type
    counts = summary['hand_type_counts']
    if counts:
        best_hand = max(counts, key=counts.get)
        print(f"\n  Favourite hand : {best_hand} ({counts[best_hand]}x)")

    print()
    divider()


def render_hand_history(hands: list) -> None:
    """
    Display a table of the last N hands.

    Args:
        hands: List of HandRecord objects from StatsTracker.last_n_hands()
    """
    if not hands:
        print("\n  No hand history yet.\n")
        return

    divider("─")
    print("  RECENT HANDS")
    divider("─")
    print(f"  {'#':>3}  {'Result':8}  {'Ended by':10}  {'Pot':>6}  {'Your hand'}")
    divider("─")

    for h in hands:
        result  = "WIN ✓" if h.winner == 'player' else ("TIE" if h.winner == 'tie' else "loss")
        ended   = h.ended_by
        hand_nm = h.player_hand_name.split('(')[0].strip() if h.player_hand_name else "—"
        print(f"  {h.hand_number:>3}  {result:8}  {ended:10}  {h.pot:>6}  {hand_nm}")

    divider("─")
    print()


def render_chip_graph(chip_history: list[dict], width: int = 40) -> None:
    """
    Render a simple ASCII line graph of chip stack over time.

    Args:
        chip_history: List of {'hand': int, 'chips': int} dicts
        width:        Character width of the graph
    """
    if len(chip_history) < 2:
        return

    chips  = [h['chips'] for h in chip_history]
    min_c  = min(chips)
    max_c  = max(chips)
    height = 8

    divider("─")
    print("  CHIP STACK HISTORY")
    divider("─")

    if max_c == min_c:
        print("  (no change in chip stack yet)\n")
        return

    # Normalise each value to a row index
    def to_row(val: int) -> int:
        return int((val - min_c) / (max_c - min_c) * (height - 1))

    # Build grid
    rows = [[' '] * len(chips) for _ in range(height)]
    for col, val in enumerate(chips):
        row = height - 1 - to_row(val)
        rows[row][col] = '●'

    # Print with y-axis labels
    for i, row in enumerate(rows):
        if i == 0:
            label = f"{max_c:>6}"
        elif i == height - 1:
            label = f"{min_c:>6}"
        elif i == height // 2:
            label = f"{(max_c + min_c) // 2:>6}"
        else:
            label = "      "
        print(f"  {label} │{''.join(row)}")

    # X-axis
    print(f"         └{'─' * len(chips)}")
    start = chip_history[0]['hand']
    end   = chip_history[-1]['hand']
    print(f"          Hand {start:<4}          Hand {end}")
    divider("─")
    print()


# ---------------------------------------------------------------------------
# Quick self-test (no game engine needed)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from deck import Deck, Card

    print("=== ui.py self-test (static render) ===\n")

    deck = Deck()
    deck.shuffle()

    from engine import GameState, Street, Winner
    from dataclasses import dataclass

    # Build a fake mid-game state for display testing
    player_hole = deck.deal(2)
    bot_hole    = deck.deal(2)
    deck.deal(1)
    board       = deck.deal(3)

    fake_state = GameState(
        player_hole  = player_hole,
        bot_hole     = bot_hole,
        board        = board,
        pot          = 120,
        player_chips = 880,
        bot_chips    = 920,
        player_bet   = 40,
        bot_bet      = 40,
        big_blind    = 20,
        street       = Street.FLOP,
        player_turn  = True,
        current_bet  = 40,
        min_raise    = 20,
    )

    render_table(fake_state, last_action_msg="Bot raised to 40.")
    print("  (static render — input prompt skipped in self-test)")
    print("\n✓ Table rendered successfully.")

    # Test stats display
    fake_summary = {
        'total_hands'      : 12,
        'player_wins'      : 7,
        'bot_wins'         : 4,
        'ties'             : 1,
        'win_rate'         : 58.3,
        'loss_rate'        : 33.3,
        'biggest_pot_won'  : 340,
        'biggest_pot_lost' : 210,
        'current_streak'   : 3,
        'best_streak'      : 5,
        'chip_history'     : [
            {'hand': i, 'chips': 1000 + (i * 15) - (i % 3) * 40}
            for i in range(1, 13)
        ],
        'hand_type_counts' : {'One Pair': 5, 'Two Pair': 3, 'Flush': 2},
    }

    from stats import HandRecord
    fake_hands = [
        HandRecord(1, 'player', 'showdown', 120, ['As','Kh'], ['Qd','Jc','Th','2s','7d'],
                   'Straight  (score: 1600)', 'One Pair  (score: 4200)', 1060, 940,
                   '2025-01-01 12:00:00'),
        HandRecord(2, 'bot',    'fold',      80, ['7s','2h'], [],
                   '', '', 1020, 980, '2025-01-01 12:05:00'),
        HandRecord(3, 'player', 'showdown',  200, ['Ah','Ad'], ['Kc','Ks','2d','5h','9c'],
                   'Two Pair  (score: 2800)', 'Two Pair  (score: 3100)', 1120, 880,
                   '2025-01-01 12:10:00'),
    ]

    render_stats_summary(fake_summary)
    render_hand_history(fake_hands)
    render_chip_graph(fake_summary['chip_history'])
    print("✓ Stats display rendered successfully.")