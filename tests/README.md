# Testing Quest Rewards & Level-Up Logic

This directory contains tests for the quest reward system and level-up mechanics.

## Unit Tests

**File**: `tests/test_quest_rewards.py`

Run with:
```bash
python -m unittest tests.test_quest_rewards
```

**Test Cases**:
- Single level-up (150 XP, level 1 → 2)
- Multi-level-up (300 XP, level 1 → 3)
- No level-up (insufficient XP)
- Already claimed rewards return None

## Verification Script

**File**: `verify_quest_rewards.py`

Run with:
```bash
python verify_quest_rewards.py
```

This script creates a test database and simulates the complete quest reward flow:
1. Creates test players at various levels
2. Awards XP and gold
3. Applies level-up logic (with proper XP overflow)
4. Verifies database state after rewards

**Output**: Creates `data/test_verification.db` which you can inspect with:
```bash
sqlite3 data/test_verification.db
```

## How It Works

### Level-Up Formula
- Level 1 → 2: Requires 100 XP (level * 100)
- Level 2 → 3: Requires 200 XP
- Level N → N+1: Requires N * 100 XP

### XP Overflow
XP carries over when leveling up. For example:
- Player at level 1 with 0 XP
- Receives 150 XP quest reward
- Levels up to 2 (costs 100 XP)
- Remaining 50 XP carries forward

### Multi-Level-Ups
If a large XP reward is received, multiple level-ups can occur:
- Player at level 1 with 0 XP
- Receives 300 XP
- Level 1 → 2 (costs 100, left 200)
- Level 2 → 3 (costs 200, left 0)
- Final: Level 3 with 0 XP

### Stat Increases Per Level
- Max Health: +10
- Max Mana: +5
- Current HP/MP: Restored to max when leveling up
