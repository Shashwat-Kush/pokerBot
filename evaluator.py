"""
evaluator.py - Hand Evaluator
===============================
Wraps the `treys` library to evaluate and compare poker hands.
This is the ONLY file in the project that imports treys directly.
Everything else calls through this interface.

Install dependency:
    pip install treys

Treys scoring:
    - Lower score = STRONGER hand
    - Score of 1     = Royal Flush (best)
    - Score of 7462  = 2-high (worst)
"""

from treys import Card as TreysCard, Evaluator as TreysEvaluator
from deck import Card


# Singleton evaluator — expensive to construct, so we build it once
_evaluator = TreysEvaluator()


# Treys rank class names mapped to friendly display strings
HAND_RANK_NAMES = {
    1: "Straight Flush",   # includes Royal Flush
    2: "Four of a Kind",
    3: "Full House",
    4: "Flush",
    5: "Straight",
    6: "Three of a Kind",
    7: "Two Pair",
    8: "One Pair",
    9: "High Card",
}


def to_treys(card: Card) -> int:
    """
    Convert our Card object to a treys integer representation.
    Treys uses bit-packed integers internally for fast evaluation.
    """
    return TreysCard.new(card.code)


def evaluate_hand(hole_cards: list[Card], board: list[Card]) -> int:
    """
    Evaluate the strength of a 5-7 card hand.

    Args:
        hole_cards: The player's 2 private cards.
        board:      The community cards (3, 4, or 5 cards depending on street).

    Returns:
        An integer score. LOWER = STRONGER.
        Range: 1 (Royal Flush) to 7462 (worst High Card).
    """
    treys_hole  = [to_treys(c) for c in hole_cards]
    treys_board = [to_treys(c) for c in board]
    return _evaluator.evaluate(treys_board, treys_hole)


def hand_rank_name(score: int) -> str:
    """
    Convert a treys score to a human-readable hand name.

    Args:
        score: The integer returned by evaluate_hand().

    Returns:
        A string like 'Full House', 'Flush', 'One Pair', etc.
    """
    rank_class = _evaluator.get_rank_class(score)
    return HAND_RANK_NAMES.get(rank_class, "Unknown Hand")


def compare_hands(
    player_hole: list[Card],
    bot_hole:    list[Card],
    board:       list[Card]
) -> str:
    """
    Compare two hands at showdown and declare the winner.

    Args:
        player_hole: The human player's 2 hole cards.
        bot_hole:    The bot's 2 hole cards.
        board:       The 5 community cards.

    Returns:
        'player' if the player wins,
        'bot'    if the bot wins,
        'tie'    if it's a split pot.
    """
    player_score = evaluate_hand(player_hole, board)
    bot_score    = evaluate_hand(bot_hole, board)

    # Lower score wins in treys
    if player_score < bot_score:
        return 'player'
    elif bot_score < player_score:
        return 'bot'
    else:
        return 'tie'


def hand_summary(hole_cards: list[Card], board: list[Card]) -> str:
    """
    One-line summary of a hand for display purposes.
    e.g.  "Full House  (score: 292)"

    Args:
        hole_cards: The player's 2 hole cards.
        board:      The 5 community cards.

    Returns:
        A formatted string summarising the hand strength.
    """
    score = evaluate_hand(hole_cards, board)
    name  = hand_rank_name(score)
    return f"{name}  (score: {score})"


# ---------------------------------------------------------------------------
# Quick self-test — run this file directly to verify everything works
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from deck import Deck

    print("=== evaluator.py self-test ===\n")

    deck = Deck()
    deck.shuffle()

    # Deal a full hand
    player_hole = deck.deal(2)
    bot_hole    = deck.deal(2)
    deck.deal(1)             # burn
    flop        = deck.deal(3)
    deck.deal(1)             # burn
    turn        = deck.deal(1)
    deck.deal(1)             # burn
    river       = deck.deal(1)
    board       = flop + turn + river

    print(f"Player hole : {player_hole[0].short()}  {player_hole[1].short()}")
    print(f"Bot hole    : {bot_hole[0].short()}  {bot_hole[1].short()}")
    print(f"Board       : {' '.join(c.short() for c in board)}")
    print()
    print(f"Player hand : {hand_summary(player_hole, board)}")
    print(f"Bot hand    : {hand_summary(bot_hole, board)}")
    print()

    result = compare_hands(player_hole, bot_hole, board)
    if result == 'player':
        print("Result: ✓ Player wins!")
    elif result == 'bot':
        print("Result: Bot wins.")
    else:
        print("Result: Split pot — Tie!")

    # Sanity check: a Royal Flush should score 1
    from deck import Card as DeckCard
    royal = [DeckCard('A','s'), DeckCard('K','s')]
    royal_board = [
        DeckCard('Q','s'), DeckCard('J','s'), DeckCard('T','s'),
        DeckCard('2','h'), DeckCard('3','d')
    ]
    score = evaluate_hand(royal, royal_board)
    assert score == 1, f"Royal Flush should score 1, got {score}"
    print(f"\n✓ Royal Flush sanity check passed (score={score}).")
    print("✓ All checks passed.")