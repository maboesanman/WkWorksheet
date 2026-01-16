import json
import numpy as np
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Rolling average period for baseline accumulation tracking
AVERAGING_PERIOD = timedelta(days=30)

# how aggressively to correct global non-periodic debt drift
DECAY_FACTOR = 0.9


def update_kanji_ledger(cache, ledger_path="kanji_ledger.json"):
    """
    Read kanji ledger, calculate elapsed time, and update debt values.

    Args:
        cache: WaniKaniCache instance
        ledger_path: Path to the kanji ledger JSON file

    Returns:
        dict: The ledger with structure {"updated_at": ISO timestamp, "baseline_accumulation": float, "target_debt": float, "kanji": {subject_id: value}}
    """
    ledger_file = Path(ledger_path)

    # Read existing ledger or create new one
    if ledger_file.exists():
        with open(ledger_file, 'r') as f:
            ledger = json.load(f)
        last_updated = datetime.fromisoformat(ledger["updated_at"])
        previous_baseline = ledger.get("baseline_accumulation", None)
    else:
        ledger = {"updated_at": None, "baseline_accumulation": 0.0, "target_debt": 0.0, "kanji": {}}
        last_updated = None
        previous_baseline = None

    # Calculate elapsed time since last update
    now = datetime.now(timezone.utc)
    if last_updated:
        elapsed = now - last_updated
    else:
        # If no previous update, use 0 elapsed time (fresh start)
        elapsed = timedelta(1)

    # Track total debt added this update
    total_debt_added = 0.0

    # Update each kanji's debt value
    for assignment in cache.get_assignments(subject_type="kanji", srs_stages=[1, 2, 3, 4, 5, 6, 7, 8]):
        subject_id = str(assignment['data']['subject_id'])
        srs_stage = int(assignment['data']['srs_stage'])

        # Get current value (default to 0 if not present)
        current_value = ledger["kanji"].get(subject_id, 0)

        if srs_stage in [1, 2, 3]:
            increment = elapsed / timedelta(days=2.5)
        elif srs_stage == 4:
            increment = elapsed / timedelta(days=2)
        elif srs_stage == 5:
            increment = elapsed / timedelta(days=7)
        elif srs_stage == 6:
            increment = elapsed / timedelta(days=14)
        elif srs_stage == 7:
            increment = elapsed / timedelta(days=30)
        elif srs_stage == 8:
            increment = elapsed / timedelta(days=120)
        else:
            increment = 0

        ledger["kanji"][subject_id] = current_value + increment
        total_debt_added += increment

    # Update baseline accumulation using rolling average
    # previous_baseline is assumed to be the average kanji added per day over AVERAGING_PERIOD
    # We weight the old average by (period - elapsed) and the new data by elapsed
    elapsed_days = elapsed / timedelta(days=1)

    new_rate = total_debt_added / elapsed_days

    print("new_rate", new_rate)

    if elapsed >= AVERAGING_PERIOD or previous_baseline == None:
        # If elapsed time exceeds averaging period, just use the new data
        new_baseline = new_rate
    else:
        # Rolling average: weighted combination of old and new
        old_weight = (AVERAGING_PERIOD - elapsed) / AVERAGING_PERIOD
        new_weight = elapsed / AVERAGING_PERIOD
        new_baseline = (previous_baseline * old_weight) + (new_rate * new_weight)

    ledger["baseline_accumulation"] = new_baseline

    # Calculate target debt: what the debt should be in a perfect system
    # target_debt = total_debt_added - baseline (positive means behind, negative means ahead)
    ledger["target_debt"] = new_rate - new_baseline

    # Update timestamp
    ledger["updated_at"] = now.isoformat()

    # Sort kanji by subject_id for easier debugging
    ledger["kanji"] = dict(sorted(ledger["kanji"].items(), key=lambda x: int(x[0])))

    out = sample_kanji_ledger(ledger, elapsed=elapsed, temperature=1.0)

    # Persist to file
    with open(ledger_file, 'w') as f:
        json.dump(ledger, indent=2, fp=f)

    return out


def sample_kanji_ledger(ledger, elapsed, temperature=1.0):
    """
    Sample kanji from the ledger using softmax with temperature.

    Repeatedly samples kanji (weighted by their debt values) and decrements them
    until the total debt is less than 0.5.

    Args:
        ledger_path: Path to the kanji ledger JSON file
        temperature: Softmax temperature (higher = more uniform, lower = more peaked)

    Returns:
        list: List of sampled subject_ids (as strings)
    """

    sampled_kanji = []

    target_debt = ledger["target_debt"]
    actual_debt = sum(ledger["kanji"].values())
    amount_to_pay = ledger["baseline_accumulation"] * elapsed / timedelta(days=1)

    correction = (actual_debt - target_debt - amount_to_pay) * (1 - DECAY_FACTOR)

    print("target debt", target_debt)
    print("actual debt", actual_debt)
    print("amount_to_pay", amount_to_pay)
    print("correction", correction)

    # pay within 0.5 of the amount_to_pay + correction
    final_threshold = actual_debt - amount_to_pay - correction + 0.5


    print("final_threshold", final_threshold)
    
    # Keep sampling until total debt < 0.5
    while sum(ledger["kanji"].values()) >= final_threshold:
        # Filter to non-negative values for sampling
        positive_kanji = {k: v for k, v in ledger["kanji"].items() if v > 0}

        if not positive_kanji:
            break

        # Prepare for softmax
        subject_ids = list(positive_kanji.keys())
        values = np.array(list(positive_kanji.values()))

        # Apply softmax with temperature
        scaled_values = values / temperature
        exp_values = np.exp(scaled_values - np.max(scaled_values))  # Subtract max for numerical stability
        probabilities = exp_values / np.sum(exp_values)

        # Sample one kanji
        sampled_idx = np.random.choice(len(subject_ids), p=probabilities)
        sampled_id = subject_ids[sampled_idx]

        # Add to results
        sampled_kanji.append(sampled_id)

        # Update ledger: set to min(value, 1) - 1
        current_value = ledger["kanji"][sampled_id]
        ledger["kanji"][sampled_id] = min(current_value, 1) - 1

    return sorted(sampled_kanji)
    