"""
deck.py - Card and Deck Management
===================================
Handles all 52 cards: representation, shuffling, dealing, and tracking.
Uses the same card string format that `treys` expects (e.g. 'As', 'Kh', '2c')
so evaluator.py can consume cards directly without any conversion.
"""

import random


# All ranks and suits in treys-compatible format
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
SUITS = ['s', 'h', 'd', 'c']  # spades, hearts, diamonds, clubs

# Human-readable display names
RANK_DISPLAY = {
    '2': '2', '3': '3', '4': '4', '5': '5', '6': '6',
    '7': '7', '8': '8', '9': '9', 'T': '10',
    'J': 'Jack', 'Q': 'Queen', 'K': 'King', 'A': 'Ace'
}

SUIT_DISPLAY = {
    's': '♠', 'h': '♥', 'd': '♦', 'c': '♣'
}

SUIT_NAMES = {
    's': 'Spades', 'h': 'Hearts', 'd': 'Diamonds', 'c': 'Clubs'
}


class Card:
    """
    Represents a single playing card.
    Stored as a 2-character string: rank + suit (e.g. 'As', 'Th', '2c')
    This matches the treys library format exactly.
    """

    def __init__(self, rank: str, suit: str):
        assert rank in RANKS, f"Invalid rank: {rank}"
        assert suit in SUITS, f"Invalid suit: {suit}"
        self.rank = rank
        self.suit = suit

    @property
    def code(self) -> str:
        """Returns the treys-compatible string e.g. 'As', 'Kh'"""
        return self.rank + self.suit

    def __str__(self) -> str:
        """Human-readable e.g. 'Ace ♠'"""
        return f"{RANK_DISPLAY[self.rank]}{SUIT_DISPLAY[self.suit]}"

    def __repr__(self) -> str:
        return f"Card('{self.code}')"

    def short(self) -> str:
        """Short display for CLI table e.g. 'A♠', 'T♥'"""
        return f"{self.rank}{SUIT_DISPLAY[self.suit]}"


class Deck:
    """
    A standard 52-card deck.

    Usage:
        deck = Deck()
        deck.shuffle()
        card = deck.deal()          # deal one card
        cards = deck.deal(5)        # deal five cards
        print(deck.remaining)       # how many cards left
    """

    def __init__(self):
        self._cards: list[Card] = []
        self._dealt: list[Card] = []
        self._build()

    def _build(self) -> None:
        """Build all 52 cards in order."""
        self._cards = [Card(rank, suit) for suit in SUITS for rank in RANKS]
        self._dealt = []

    def shuffle(self) -> None:
        """Shuffle the undealt cards. Call this before every new hand."""
        self._build()                  # reset — put dealt cards back
        random.shuffle(self._cards)

    def deal(self, n: int = 1) -> list[Card]:
        """
        Deal n cards from the top of the deck.
        Raises ValueError if not enough cards remain.
        Returns a list even when n=1 for consistency.
        """
        if n > self.remaining:
            raise ValueError(
                f"Cannot deal {n} cards — only {self.remaining} remaining."
            )
        dealt = self._cards[:n]
        self._cards = self._cards[n:]
        self._dealt.extend(dealt)
        return dealt

    def deal_one(self) -> Card:
        """Convenience method: deal exactly one card and return it directly."""
        return self.deal(1)[0]

    @property
    def remaining(self) -> int:
        """Number of cards still in the deck."""
        return len(self._cards)

    @property
    def dealt_count(self) -> int:
        """Number of cards that have been dealt this hand."""
        return len(self._dealt)

    def __repr__(self) -> str:
        return f"Deck({self.remaining} cards remaining)"


# ---------------------------------------------------------------------------
# Quick self-test — run this file directly to verify everything works
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== deck.py self-test ===\n")

    deck = Deck()
    deck.shuffle()
    print(f"Fresh shuffled deck: {deck}")

    # Deal 2 hole cards
    hole = deck.deal(2)
    print(f"\nYour hole cards: {hole[0]}  {hole[1]}")
    print(f"  (treys codes):  {hole[0].code}  {hole[1].code}")
    print(f"  (short form):   {hole[0].short()}  {hole[1].short()}")

    # Deal the flop (burn 1, deal 3)
    deck.deal_one()           # burn card
    flop = deck.deal(3)
    print(f"\nFlop: {flop[0]}  {flop[1]}  {flop[2]}")

    # Deal the turn
    deck.deal_one()           # burn card
    turn = deck.deal_one()
    print(f"Turn: {turn}")

    # Deal the river
    deck.deal_one()           # burn card
    river = deck.deal_one()
    print(f"River: {river}")

    print(f"\nCards remaining: {deck.remaining}  |  Cards dealt: {deck.dealt_count}")
    assert deck.remaining + deck.dealt_count == 52, "Card count mismatch!"
    print("\n✓ All checks passed.")