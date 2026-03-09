"""
stats.py - Statistics Tracker
================================
Tracks hand results across sessions. Saves to stats.json automatically.
No display logic lives here — that's ui.py's job.

Tracks per hand:
  - Winner (player / bot / tie)
  - How it ended (showdown / fold)
  - Pot size
  - Your hole cards
  - Board cards
  - Hand names at showdown
  - Chip stacks after the hand

Calculates across all hands:
  - Win / loss / tie counts and rates
  - Biggest pot won and lost
  - Current win streak / best win streak
  - Chip stack history (for graph)
  - Most common winning hand type
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime    import datetime
from engine      import GameState, Street, Winner


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

STATS_FILE = "stats.json"


# ---------------------------------------------------------------------------
# Hand record
# ---------------------------------------------------------------------------

@dataclass
class HandRecord:
    hand_number      : int
    winner           : str          # 'player', 'bot', 'tie'
    ended_by         : str          # 'showdown', 'fold'
    pot              : int
    player_hole      : list[str]    # e.g. ['As', 'Kh']
    board            : list[str]    # e.g. ['Qd', 'Jc', 'Th', '2s', '7d']
    player_hand_name : str          # e.g. 'Straight'
    bot_hand_name    : str
    player_chips_after : int
    bot_chips_after    : int
    timestamp        : str


# ---------------------------------------------------------------------------
# Stats manager
# ---------------------------------------------------------------------------

class StatsTracker:
    """
    Tracks hand history and computes summary statistics.
    Persists data to a local JSON file between sessions.

    Usage:
        tracker = StatsTracker()
        tracker.record_hand(final_state, hand_number, ended_by_fold=False)
        summary = tracker.summary()
    """

    def __init__(self, filepath: str = STATS_FILE):
        self.filepath = filepath
        self.hands: list[HandRecord] = []
        self._load()

    # -----------------------------------------------------------------------
    # Recording
    # -----------------------------------------------------------------------

    def record_hand(
        self,
        state       : GameState,
        hand_number : int,
        folder      : str | None = None   # 'player' or 'bot' if ended by fold
    ) -> None:
        """
        Record the result of a completed hand.

        Args:
            state:       Final GameState after hand ends.
            hand_number: Sequential hand number this session.
            folder:      If hand ended by fold, who folded ('player' or 'bot').
                         None if hand went to showdown.
        """
        ended_by = 'fold' if folder else 'showdown'

        record = HandRecord(
            hand_number        = hand_number,
            winner             = state.winner.value,
            ended_by           = ended_by,
            pot                = state.pot if state.pot > 0 else self._last_pot(state),
            player_hole        = [c.code for c in state.player_hole],
            board              = [c.code for c in state.board],
            player_hand_name   = state.player_hand_name,
            bot_hand_name      = state.bot_hand_name,
            player_chips_after = state.player_chips,
            bot_chips_after    = state.bot_chips,
            timestamp          = datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        self.hands.append(record)
        self._save()

    # -----------------------------------------------------------------------
    # Summary statistics
    # -----------------------------------------------------------------------

    def summary(self) -> dict:
        """
        Compute summary statistics across all recorded hands.

        Returns a dict with keys:
          total_hands, player_wins, bot_wins, ties,
          win_rate, loss_rate,
          biggest_pot_won, biggest_pot_lost,
          current_streak, best_streak,
          chip_history, hand_type_counts,
          session_hands (hands this session only)
        """
        if not self.hands:
            return self._empty_summary()

        total   = len(self.hands)
        p_wins  = sum(1 for h in self.hands if h.winner == 'player')
        b_wins  = sum(1 for h in self.hands if h.winner == 'bot')
        ties    = sum(1 for h in self.hands if h.winner == 'tie')

        # Biggest pots
        won_hands  = [h for h in self.hands if h.winner == 'player']
        lost_hands = [h for h in self.hands if h.winner == 'bot']
        biggest_won  = max((h.pot for h in won_hands),  default=0)
        biggest_lost = max((h.pot for h in lost_hands), default=0)

        # Streak tracking
        current_streak, best_streak = self._compute_streaks()

        # Chip history (one entry per hand)
        chip_history = [
            {'hand': h.hand_number, 'chips': h.player_chips_after}
            for h in self.hands
        ]

        # Most common hand types at showdown (player's hands)
        hand_type_counts: dict[str, int] = {}
        for h in self.hands:
            if h.ended_by == 'showdown' and h.player_hand_name:
                # Extract just the hand name (strip score suffix)
                name = h.player_hand_name.split('(')[0].strip()
                hand_type_counts[name] = hand_type_counts.get(name, 0) + 1

        return {
            'total_hands'    : total,
            'player_wins'    : p_wins,
            'bot_wins'       : b_wins,
            'ties'           : ties,
            'win_rate'       : round(p_wins / total * 100, 1) if total else 0,
            'loss_rate'      : round(b_wins / total * 100, 1) if total else 0,
            'biggest_pot_won'  : biggest_won,
            'biggest_pot_lost' : biggest_lost,
            'current_streak' : current_streak,
            'best_streak'    : best_streak,
            'chip_history'   : chip_history,
            'hand_type_counts': hand_type_counts,
        }

    def last_n_hands(self, n: int = 5) -> list[HandRecord]:
        """Return the last N hand records."""
        return self.hands[-n:]

    def reset(self) -> None:
        """Wipe all history. Irreversible."""
        self.hands = []
        self._save()

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

    def _save(self) -> None:
        """Serialize hands to JSON file."""
        data = [asdict(h) for h in self.hands]
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def _load(self) -> None:
        """Load hands from JSON file if it exists."""
        if not os.path.exists(self.filepath):
            self.hands = []
            return
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
            self.hands = [HandRecord(**h) for h in data]
        except (json.JSONDecodeError, TypeError):
            # Corrupted file — start fresh
            self.hands = []

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _compute_streaks(self) -> tuple[int, int]:
        """
        Compute current win streak and best win streak.
        Returns (current_streak, best_streak).
        Losses and ties reset the streak.
        """
        best    = 0
        current = 0
        for h in self.hands:
            if h.winner == 'player':
                current += 1
                best = max(best, current)
            else:
                current = 0
        return current, best

    def _last_pot(self, state: GameState) -> int:
        """
        When a fold ends the hand, the pot has already been awarded
        and reset to 0. Reconstruct it from chip stacks if needed.
        """
        if self.hands:
            prev = self.hands[-1]
            total_prev = prev.player_chips_after + prev.bot_chips_after
            total_now  = state.player_chips + state.bot_chips
            return abs(total_prev - total_now)
        return 0

    def _empty_summary(self) -> dict:
        return {
            'total_hands'      : 0,
            'player_wins'      : 0,
            'bot_wins'         : 0,
            'ties'             : 0,
            'win_rate'         : 0.0,
            'loss_rate'        : 0.0,
            'biggest_pot_won'  : 0,
            'biggest_pot_lost' : 0,
            'current_streak'   : 0,
            'best_streak'      : 0,
            'chip_history'     : [],
            'hand_type_counts' : {},
        }


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import os

    TEST_FILE = "stats_test.json"

    # Clean slate
    if os.path.exists(TEST_FILE):
        os.remove(TEST_FILE)

    tracker = StatsTracker(filepath=TEST_FILE)

    # Simulate recording 5 fake hands
    from deck   import Deck
    from engine import GameEngine, Action, Winner
    from engine import Street
    import dataclasses

    engine = GameEngine(starting_chips=1000, big_blind=20)

    print("=== stats.py self-test ===\n")

    for i in range(5):
        state = engine.start_hand(player_is_dealer=(i % 2 == 0))
        while engine.hand_active:
            if state.player_turn:
                state = engine.apply_action(
                    Action.CHECK if state.amount_to_call() == 0 else Action.CALL
                )
            else:
                state = engine.apply_action(
                    Action.CHECK if state.amount_to_call() == 0 else Action.CALL
                )

        folder = None
        if state.street == Street.HAND_OVER:
            folder = 'player' if state.winner == Winner.BOT else 'bot'

        tracker.record_hand(state, hand_number=i+1, folder=folder)
        print(f"Hand {i+1}: winner={state.winner.value}  chips={state.player_chips}")

    s = tracker.summary()
    print(f"\n── Summary ──────────────────")
    print(f"Total hands    : {s['total_hands']}")
    print(f"Win rate       : {s['win_rate']}%")
    print(f"Player wins    : {s['player_wins']}")
    print(f"Bot wins       : {s['bot_wins']}")
    print(f"Biggest pot won: {s['biggest_pot_won']}")
    print(f"Current streak : {s['current_streak']}")
    print(f"Best streak    : {s['best_streak']}")
    print(f"Chip history   : {s['chip_history']}")

    # Verify persistence
    tracker2 = StatsTracker(filepath=TEST_FILE)
    assert len(tracker2.hands) == 5, "Persistence failed"
    print(f"\n✓ Persistence verified ({len(tracker2.hands)} hands loaded)")

    # Cleanup
    os.remove(TEST_FILE)
    print("✓ All stats checks passed.")