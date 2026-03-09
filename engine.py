"""
engine.py - Game Engine / State Machine
=========================================
The heart of the poker bot. Tracks all game state and enforces the rules.
Does NOT display anything and does NOT make decisions — that's ui.py and bot.py.

Heads-up Texas Hold'em rules used here:
  - Dealer = Small Blind (SB) in heads-up
  - Non-dealer = Big Blind (BB)
  - BB acts first pre-flop (after the SB opens)
  - SB acts first on all post-flop streets
  - Minimum raise = size of the previous raise (or BB if no raise yet)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from deck import Deck, Card


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Street(Enum):
    PREFLOP  = auto()
    FLOP     = auto()
    TURN     = auto()
    RIVER    = auto()
    SHOWDOWN = auto()
    HAND_OVER = auto()   # someone folded — hand ended early


class Action(Enum):
    FOLD  = "fold"
    CALL  = "call"
    RAISE = "raise"
    CHECK = "check"


class Winner(Enum):
    PLAYER = "player"
    BOT    = "bot"
    TIE    = "tie"


# ---------------------------------------------------------------------------
# State snapshot (read-only view passed to bot and UI)
# ---------------------------------------------------------------------------

@dataclass
class GameState:
    # Cards
    player_hole : list[Card]
    bot_hole    : list[Card]
    board       : list[Card]

    # Money
    pot          : int
    player_chips : int
    bot_chips    : int
    player_bet   : int        # amount player has put in THIS street
    bot_bet      : int        # amount bot has put in THIS street
    big_blind    : int

    # Street / turn
    street       : Street
    player_turn  : bool       # True = player acts, False = bot acts

    # Betting constraints
    current_bet  : int        # highest bet on the table this street
    min_raise    : int        # minimum total raise amount

    # End-of-hand info (populated after SHOWDOWN or HAND_OVER)
    winner       : Winner | None = None
    player_hand_name : str   = ""
    bot_hand_name    : str   = ""

    def to_act(self) -> str:
        return "player" if self.player_turn else "bot"

    def amount_to_call(self) -> int:
        """How much the acting player needs to put in to call."""
        if self.player_turn:
            return self.current_bet - self.player_bet
        else:
            return self.current_bet - self.bot_bet


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class GameEngine:
    """
    Manages one full hand of heads-up Texas Hold'em.

    Usage:
        engine = GameEngine(starting_chips=1000, big_blind=20)
        state  = engine.start_hand(player_is_dealer=True)

        while state.street not in (Street.SHOWDOWN, Street.HAND_OVER):
            action, amount = get_action(state)   # from UI or bot
            state = engine.apply_action(action, amount)
    """

    def __init__(self, starting_chips: int = 1000, big_blind: int = 20):
        self.big_blind      = big_blind
        self.small_blind    = big_blind // 2

        self.player_chips   = starting_chips
        self.bot_chips      = starting_chips

        self.deck           = Deck()

        # Hand state — reset each hand
        self._pot           = 0
        self._player_hole   : list[Card] = []
        self._bot_hole      : list[Card] = []
        self._board         : list[Card] = []
        self._street        = Street.PREFLOP
        self._player_is_dealer = True

        # Betting state — reset each street
        self._player_bet    = 0
        self._bot_bet       = 0
        self._current_bet   = 0
        self._min_raise     = big_blind
        self._player_turn   = True

        # Track whether both players have acted on this street
        # (needed to detect when a street is complete)
        self._actions_this_street = 0
        self._last_aggressor : str | None = None   # 'player' or 'bot'

        self._winner : Winner | None = None
        self._player_hand_name = ""
        self._bot_hand_name    = ""

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def start_hand(self, player_is_dealer: bool = True) -> GameState:
        """
        Shuffle, post blinds, deal hole cards, and return the opening state.
        Call this at the beginning of every new hand.
        """
        self._player_is_dealer = player_is_dealer
        self._reset_hand()

        # Post blinds
        # In heads-up: dealer = SB, non-dealer = BB
        if player_is_dealer:
            sb_name, bb_name = 'player', 'bot'
        else:
            sb_name, bb_name = 'bot', 'player'

        self._post_blind(sb_name, self.small_blind)
        self._post_blind(bb_name, self.big_blind)
        self._current_bet = self.big_blind
        self._min_raise   = self.big_blind

        # Pre-flop: SB (dealer) acts first in heads-up
        self._player_turn = (sb_name == 'player')

        # Deal hole cards
        self._player_hole = self.deck.deal(2)
        self._bot_hole    = self.deck.deal(2)

        return self._snapshot()

    def apply_action(self, action: Action, raise_amount: int = 0) -> GameState:
        """
        Apply a player or bot action and advance the game state.

        Args:
            action:       One of Action.FOLD, CALL, RAISE, CHECK
            raise_amount: Total chips to put in (only used for RAISE).
                          Must be >= min_raise and <= acting player's stack.

        Returns:
            Updated GameState snapshot.
        """
        acting = 'player' if self._player_turn else 'bot'

        if action == Action.FOLD:
            self._handle_fold(acting)

        elif action == Action.CHECK:
            self._handle_check(acting)

        elif action == Action.CALL:
            self._handle_call(acting)

        elif action == Action.RAISE:
            self._handle_raise(acting, raise_amount)

        # After action, check if street is over
        if self._street not in (Street.SHOWDOWN, Street.HAND_OVER):
            if self._street_is_over():
                self._advance_street()

        return self._snapshot()

    def valid_actions(self) -> list[Action]:
        """
        Return the list of legal actions for the currently acting player.
        CHECK is only legal when the acting player's bet matches current_bet.
        """
        acting_bet = self._player_bet if self._player_turn else self._bot_bet
        actions = [Action.FOLD, Action.CALL, Action.RAISE]
        if acting_bet == self._current_bet:
            actions.append(Action.CHECK)
            actions.remove(Action.CALL)   # can't call when you can check
        return actions

    @property
    def hand_active(self) -> bool:
        return self._street not in (Street.SHOWDOWN, Street.HAND_OVER)

    # -----------------------------------------------------------------------
    # Action handlers
    # -----------------------------------------------------------------------

    def _handle_fold(self, acting: str) -> None:
        # The other player wins the pot
        if acting == 'player':
            self.bot_chips   += self._pot
            self._winner      = Winner.BOT
        else:
            self.player_chips += self._pot
            self._winner       = Winner.PLAYER
        self._pot    = 0
        self._street = Street.HAND_OVER

    def _handle_check(self, acting: str) -> None:
        self._actions_this_street += 1
        self._switch_turn()

    def _handle_call(self, acting: str) -> None:
        amount = self._current_bet - self._get_bet(acting)
        chips  = self._get_chips(acting)
        amount = min(amount, chips)   # handle all-in (simplified)

        self._deduct_chips(acting, amount)
        self._add_to_bet(acting, amount)
        self._pot += amount
        self._actions_this_street += 1
        self._switch_turn()

    def _handle_raise(self, acting: str, raise_amount: int) -> None:
        """
        raise_amount = the TOTAL chips the acting player wants to have
        committed this street after the raise.
        e.g. if current_bet=40 and player already put in 20, a raise to 80
        means raise_amount=80 and they put in 60 more chips.
        """
        already_in   = self._get_bet(acting)
        extra_needed = raise_amount - already_in
        chips        = self._get_chips(acting)
        extra_needed = min(extra_needed, chips)   # all-in cap

        self._deduct_chips(acting, extra_needed)
        self._add_to_bet(acting, extra_needed)
        self._pot += extra_needed

        self._min_raise    = raise_amount - self._current_bet
        self._current_bet  = raise_amount
        self._last_aggressor = acting
        self._actions_this_street += 1
        self._switch_turn()

    # -----------------------------------------------------------------------
    # Street management
    # -----------------------------------------------------------------------

    def _street_is_over(self) -> bool:
        """
        A street ends when:
          1. Both players have acted at least once, AND
          2. Both players have equal bets (or one is all-in)
        """
        if self._actions_this_street < 2:
            return False
        return self._player_bet == self._bot_bet

    def _advance_street(self) -> None:
        """Move to the next street and deal community cards."""
        self._reset_street_bets()

        if self._street == Street.PREFLOP:
            self.deck.deal(1)             # burn
            self._board += self.deck.deal(3)
            self._street = Street.FLOP

        elif self._street == Street.FLOP:
            self.deck.deal(1)             # burn
            self._board += self.deck.deal(1)
            self._street = Street.TURN

        elif self._street == Street.TURN:
            self.deck.deal(1)             # burn
            self._board += self.deck.deal(1)
            self._street = Street.RIVER

        elif self._street == Street.RIVER:
            self._resolve_showdown()
            return

        # Post-flop: non-dealer (BB pre-flop) acts first
        # In heads-up that's whoever is NOT the dealer
        if self._player_is_dealer:
            self._player_turn = False   # bot (BB) acts first post-flop
        else:
            self._player_turn = True    # player (BB) acts first post-flop

    def _resolve_showdown(self) -> None:
        """Evaluate hands, award the pot, and set winner info."""
        from evaluator import compare_hands, hand_summary

        result = compare_hands(self._player_hole, self._bot_hole, self._board)

        self._player_hand_name = hand_summary(self._player_hole, self._board)
        self._bot_hand_name    = hand_summary(self._bot_hole, self._board)

        if result == 'player':
            self.player_chips += self._pot
            self._winner = Winner.PLAYER
        elif result == 'bot':
            self.bot_chips += self._pot
            self._winner = Winner.BOT
        else:
            half = self._pot // 2
            self.player_chips += half
            self.bot_chips    += half + (self._pot % 2)  # odd chip to bot
            self._winner = Winner.TIE

        self._pot    = 0
        self._street = Street.SHOWDOWN

    # -----------------------------------------------------------------------
    # Helper utilities
    # -----------------------------------------------------------------------

    def _reset_hand(self) -> None:
        self.deck.shuffle()
        self._pot              = 0
        self._player_hole      = []
        self._bot_hole         = []
        self._board            = []
        self._street           = Street.PREFLOP
        self._winner           = None
        self._player_hand_name = ""
        self._bot_hand_name    = ""
        self._reset_street_bets()

    def _reset_street_bets(self) -> None:
        self._player_bet          = 0
        self._bot_bet             = 0
        self._current_bet         = 0
        self._min_raise           = self.big_blind
        self._actions_this_street = 0
        self._last_aggressor      = None

    def _post_blind(self, who: str, amount: int) -> None:
        actual = min(amount, self._get_chips(who))
        self._deduct_chips(who, actual)
        self._add_to_bet(who, actual)
        self._pot += actual

    def _switch_turn(self) -> None:
        self._player_turn = not self._player_turn

    def _get_chips(self, who: str) -> int:
        return self.player_chips if who == 'player' else self.bot_chips

    def _get_bet(self, who: str) -> int:
        return self._player_bet if who == 'player' else self._bot_bet

    def _deduct_chips(self, who: str, amount: int) -> None:
        if who == 'player':
            self.player_chips -= amount
        else:
            self.bot_chips -= amount

    def _add_to_bet(self, who: str, amount: int) -> None:
        if who == 'player':
            self._player_bet += amount
        else:
            self._bot_bet += amount

    def _snapshot(self) -> GameState:
        return GameState(
            player_hole      = list(self._player_hole),
            bot_hole         = list(self._bot_hole),
            board            = list(self._board),
            pot              = self._pot,
            player_chips     = self.player_chips,
            bot_chips        = self.bot_chips,
            player_bet       = self._player_bet,
            bot_bet          = self._bot_bet,
            big_blind        = self.big_blind,
            street           = self._street,
            player_turn      = self._player_turn,
            current_bet      = self._current_bet,
            min_raise        = self._min_raise,
            winner           = self._winner,
            player_hand_name = self._player_hand_name,
            bot_hand_name    = self._bot_hand_name,
        )


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== engine.py self-test ===\n")

    engine = GameEngine(starting_chips=1000, big_blind=20)
    state  = engine.start_hand(player_is_dealer=True)

    print(f"Street : {state.street.name}")
    print(f"Pot    : {state.pot}")
    print(f"Player chips: {state.player_chips}  |  Bot chips: {state.bot_chips}")
    print(f"Player hole : {state.player_hole[0].short()} {state.player_hole[1].short()}")
    print(f"To act : {state.to_act()}")
    print(f"Valid  : {[a.value for a in engine.valid_actions()]}")
    print()

    # Simulate: player calls, bot checks → flop
    state = engine.apply_action(Action.CALL)
    print(f"After player call  → to act: {state.to_act()}  pot: {state.pot}")

    state = engine.apply_action(Action.CHECK)
    print(f"After bot check    → street: {state.street.name}  board: {' '.join(c.short() for c in state.board)}")

    # Bet the flop: player checks, bot checks → turn
    state = engine.apply_action(Action.CHECK)
    state = engine.apply_action(Action.CHECK)
    print(f"After flop checks  → street: {state.street.name}  board: {' '.join(c.short() for c in state.board)}")

    # Turn: player raises, bot calls → river
    state = engine.apply_action(Action.RAISE, raise_amount=40)
    state = engine.apply_action(Action.CALL)
    print(f"After turn raise/call → street: {state.street.name}  board: {' '.join(c.short() for c in state.board)}")

    # River: both check → showdown
    state = engine.apply_action(Action.CHECK)
    state = engine.apply_action(Action.CHECK)
    print(f"\nShowdown!")
    print(f"  Player: {state.player_hand_name}")
    print(f"  Bot   : {state.bot_hand_name}")
    print(f"  Winner: {state.winner.value}")
    print(f"  Player chips: {state.player_chips}  |  Bot chips: {state.bot_chips}")
    print("\n✓ Full hand completed successfully.")