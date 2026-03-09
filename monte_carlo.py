"""
monte_carlo.py - Monte Carlo Equity Estimator
===============================================
Estimates the bot's win probability by simulating thousands of random
hand runouts. This is the mathematical core of the Level 2 bot.

How it works:
  1. Build a deck with all known cards removed (bot hole + current board)
  2. Randomly sample an opponent hand + remaining community cards
  3. Evaluate who wins using treys
  4. Repeat N times and return wins / total

Typical performance:
  - 500  simulations ≈ 2–5ms   (fast, slightly noisy)
  - 1000 simulations ≈ 5–10ms  (recommended balance)
  - 2000 simulations ≈ 10–20ms (high accuracy)

Usage:
    from monte_carlo import estimate_equity
    equity = estimate_equity(bot_hole, board, simulations=1000)
    # equity = 0.0 to 1.0 (e.g. 0.72 means bot wins ~72% of runouts)
"""

import random
from deck      import Card, RANKS, SUITS
from evaluator import evaluate_hand


# ---------------------------------------------------------------------------
# Core simulation
# ---------------------------------------------------------------------------

def estimate_equity(
    bot_hole    : list[Card],
    board       : list[Card],
    simulations : int = 1000
) -> float:
    """
    Estimate the bot's win probability via Monte Carlo simulation.

    Args:
        bot_hole:    The bot's 2 hole cards.
        board:       Community cards dealt so far (0, 3, 4, or 5 cards).
        simulations: Number of random runouts to simulate.

    Returns:
        A float between 0.0 and 1.0 representing win probability.
        Ties count as 0.5 wins.
    """
    # Build the pool of cards not yet seen
    known_codes  = {c.code for c in bot_hole + board}
    remaining    = [
        Card(rank, suit)
        for suit in SUITS
        for rank in RANKS
        if (rank + suit) not in known_codes
    ]

    cards_needed_on_board = 5 - len(board)  # how many community cards still to come
    wins  = 0.0
    total = 0

    for _ in range(simulations):
        # Shuffle the unseen deck
        random.shuffle(remaining)

        # Deal 2 cards to the opponent
        opp_hole = remaining[:2]

        # Deal remaining community cards
        runout_board = board + remaining[2 : 2 + cards_needed_on_board]

        # Need exactly 5 board cards to evaluate
        if len(runout_board) != 5:
            continue

        # Evaluate both hands
        bot_score = evaluate_hand(bot_hole,  runout_board)
        opp_score = evaluate_hand(opp_hole, runout_board)

        # Lower score = stronger hand in treys
        if bot_score < opp_score:
            wins += 1.0      # win
        elif bot_score == opp_score:
            wins += 0.5      # tie counts as half a win

        total += 1

    if total == 0:
        return 0.5  # fallback: no data, assume even

    return wins / total


# ---------------------------------------------------------------------------
# Pot odds helper (lives here since it's used alongside equity)
# ---------------------------------------------------------------------------

def pot_odds(to_call: int, pot: int) -> float:
    """
    Calculate the pot odds the bot is being offered.

    Args:
        to_call: Chips required to call.
        pot:     Current pot size (before the call).

    Returns:
        A float between 0.0 and 1.0.
        e.g. to_call=50, pot=100 → pot_odds=0.333 (need 33% equity to call)

    If to_call is 0 (free check), returns 0.0 — always worth seeing the card.
    """
    if to_call <= 0:
        return 0.0
    return to_call / (pot + to_call)


def has_positive_ev(equity: float, to_call: int, pot: int) -> bool:
    """
    Returns True if calling has positive expected value.
    i.e. equity > pot_odds

    Args:
        equity:  Win probability from estimate_equity().
        to_call: Chips required to call.
        pot:     Current pot size.
    """
    return equity > pot_odds(to_call, pot)


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from deck import Deck

    print("=== monte_carlo.py self-test ===\n")

    # Test 1: Pocket Aces pre-flop should have ~85% equity heads-up
    from deck import Card as C
    aa_hole  = [C('A', 's'), C('A', 'h')]
    equity   = estimate_equity(aa_hole, board=[], simulations=2000)
    print(f"Pocket Aces pre-flop equity  : {equity:.1%}  (expect ~85%)")
    assert 0.75 < equity < 0.95, f"Unexpected equity: {equity:.1%}"

    # Test 2: 72 offsuit pre-flop should have ~35% equity
    trash_hole = [C('7', 's'), C('2', 'h')]
    equity2    = estimate_equity(trash_hole, board=[], simulations=2000)
    print(f"7-2 offsuit pre-flop equity  : {equity2:.1%}  (expect ~35%)")
    assert 0.25 < equity2 < 0.50, f"Unexpected equity: {equity2:.1%}"

    # Test 3: Made flush on the flop should be very strong
    flush_hole  = [C('K', 'h'), C('Q', 'h')]
    flush_board = [C('J', 'h'), C('T', 'h'), C('2', 'h')]
    equity3     = estimate_equity(flush_hole, flush_board, simulations=2000)
    print(f"King-high flush on flop      : {equity3:.1%}  (expect ~85%+)")
    assert equity3 > 0.75, f"Unexpected equity: {equity3:.1%}"

    # Test 4: Pot odds check
    odds = pot_odds(to_call=100, pot=100)
    print(f"\nPot odds (call 100 into 100) : {odds:.1%}  (expect 50%)")
    assert abs(odds - 0.5) < 0.01

    odds2 = pot_odds(to_call=500, pot=50)
    print(f"Pot odds (call 500 into 50)  : {odds2:.1%}  (expect ~91%) ← big bluff")
    assert odds2 > 0.85

    # Test 5: has_positive_ev
    assert has_positive_ev(0.72, 50, 100) == True   # 72% equity vs 33% pot odds
    assert has_positive_ev(0.20, 50, 100) == False  # 20% equity vs 33% pot odds
    print(f"\nEV checks passed.")

    print("\n✓ All monte_carlo checks passed.")