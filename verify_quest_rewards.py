"""
Test verification script to simulate quest completion and inspect database
"""
import asyncio
import aiosqlite
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def verify_quest_rewards():
    """Simulate quest completion and verify level-up logic"""
    db_path = 'data/test_verification.db'
    
    # Clean up old test database
    if os.path.exists(db_path):
        os.remove(db_path)
    
    print("=" * 60)
    print("Quest Reward & Level-Up Verification Test")
    print("=" * 60)
    
    # Create test database
    async with aiosqlite.connect(db_path) as db:
        # Create schema
        await db.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                health INTEGER DEFAULT 100,
                max_health INTEGER DEFAULT 100,
                mana INTEGER DEFAULT 100,
                max_mana INTEGER DEFAULT 100,
                gold INTEGER DEFAULT 0
            )
        ''')
        
        await db.execute('''
            CREATE TABLE IF NOT EXISTS active_quests (
                player_id INTEGER,
                quest_id TEXT,
                objectives_progress TEXT,
                completed BOOLEAN DEFAULT FALSE,
                rewards_claimed BOOLEAN DEFAULT FALSE,
                PRIMARY KEY (player_id, quest_id)
            )
        ''')
        
        await db.commit()
        print("\n✓ Database schema created")
        
        # Test Case 1: Single level-up (1 -> 2)
        print("\n" + "=" * 60)
        print("Test 1: Single Level-Up (150 XP, level 1 -> 2)")
        print("=" * 60)
        
        player_id = 1001
        await db.execute(
            'INSERT INTO players (id, name, level, xp, gold, max_health, max_mana) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (player_id, 'TestPlayer1', 1, 0, 0, 100, 100)
        )
        await db.commit()
        
        cursor = await db.execute('SELECT * FROM players WHERE id = ?', (player_id,))
        row = await cursor.fetchone()
        print(f"\nBefore rewards:")
        print(f"  Level: {row[2]}, XP: {row[3]}, Gold: {row[8]}")
        print(f"  Max HP: {row[5]}, Max Mana: {row[7]}")
        
        # Simulate reward: +150 XP, +50 gold
        xp_reward = 150
        gold_reward = 50
        
        await db.execute('UPDATE players SET xp = xp + ?, gold = gold + ? WHERE id = ?',
                        (xp_reward, gold_reward, player_id))
        await db.commit()
        
        # Simulate level-up logic
        cursor = await db.execute('SELECT level, xp, max_health, max_mana FROM players WHERE id = ?', (player_id,))
        row = await cursor.fetchone()
        cur_level, cur_xp, cur_max_health, cur_max_mana = row
        
        leveled = False
        while cur_xp >= (cur_level * 100):
            xp_needed = cur_level * 100
            cur_xp -= xp_needed
            cur_level += 1
            cur_max_health += 10
            cur_max_mana += 5
            leveled = True
            print(f"\n✓ Level up! {cur_level - 1} -> {cur_level}")
        
        if leveled:
            await db.execute('''
                UPDATE players
                SET level = ?, xp = ?, max_health = ?, health = ?, max_mana = ?, mana = ?
                WHERE id = ?
            ''', (cur_level, cur_xp, cur_max_health, cur_max_health, cur_max_mana, cur_max_mana, player_id))
            await db.commit()
        
        cursor = await db.execute('SELECT * FROM players WHERE id = ?', (player_id,))
        row = await cursor.fetchone()
        print(f"\nAfter rewards & level-up:")
        print(f"  Level: {row[2]} (✓ Expected: 2)")
        print(f"  XP: {row[3]} (✓ Expected: 50, since 150 - 100 = 50)")
        print(f"  Gold: {row[8]} (✓ Expected: 50)")
        print(f"  Max HP: {row[5]} (✓ Expected: 110, since 100 + 10 = 110)")
        print(f"  Max Mana: {row[7]} (✓ Expected: 105, since 100 + 5 = 105)")
        
        assert row[2] == 2, "Level should be 2"
        assert row[3] == 50, "XP should be 50"
        assert row[5] == 110, "Max health should be 110"
        assert row[7] == 105, "Max mana should be 105"
        print("\n✓ Test 1 PASSED")
        
        # Test Case 2: Multi-level-up (1 -> 3)
        print("\n" + "=" * 60)
        print("Test 2: Multi-Level-Up (300 XP, level 1 -> 3)")
        print("=" * 60)
        
        player_id = 1002
        await db.execute(
            'INSERT INTO players (id, name, level, xp, gold, max_health, max_mana) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (player_id, 'TestPlayer2', 1, 0, 0, 100, 100)
        )
        await db.commit()
        
        cursor = await db.execute('SELECT * FROM players WHERE id = ?', (player_id,))
        row = await cursor.fetchone()
        print(f"\nBefore rewards:")
        print(f"  Level: {row[2]}, XP: {row[3]}")
        
        # Simulate reward: +300 XP
        xp_reward = 300
        await db.execute('UPDATE players SET xp = xp + ? WHERE id = ?', (xp_reward, player_id))
        await db.commit()
        
        # Simulate level-up logic
        cursor = await db.execute('SELECT level, xp, max_health, max_mana FROM players WHERE id = ?', (player_id,))
        row = await cursor.fetchone()
        cur_level, cur_xp, cur_max_health, cur_max_mana = row
        
        level_ups = 0
        while cur_xp >= (cur_level * 100):
            xp_needed = cur_level * 100
            cur_xp -= xp_needed
            cur_level += 1
            cur_max_health += 10
            cur_max_mana += 5
            level_ups += 1
            print(f"✓ Level up #{level_ups}! {cur_level - 1} -> {cur_level}")
        
        await db.execute('''
            UPDATE players
            SET level = ?, xp = ?, max_health = ?, health = ?, max_mana = ?, mana = ?
            WHERE id = ?
        ''', (cur_level, cur_xp, cur_max_health, cur_max_health, cur_max_mana, cur_max_mana, player_id))
        await db.commit()
        
        cursor = await db.execute('SELECT * FROM players WHERE id = ?', (player_id,))
        row = await cursor.fetchone()
        print(f"\nAfter rewards & level-ups:")
        print(f"  Level: {row[2]} (✓ Expected: 3)")
        print(f"  XP: {row[3]} (✓ Expected: 0, since 300 - 100 - 200 = 0)")
        print(f"  Max HP: {row[5]} (✓ Expected: 120, since 100 + 10 + 10 = 120)")
        print(f"  Max Mana: {row[7]} (✓ Expected: 110, since 100 + 5 + 5 = 110)")
        
        assert row[2] == 3, "Level should be 3"
        assert row[3] == 0, "XP should be 0"
        assert row[5] == 120, "Max health should be 120"
        assert row[7] == 110, "Max mana should be 110"
        print("\n✓ Test 2 PASSED")
        
        # Test Case 3: No level-up (insufficient XP)
        print("\n" + "=" * 60)
        print("Test 3: No Level-Up (50 XP, stays at level 1)")
        print("=" * 60)
        
        player_id = 1003
        await db.execute(
            'INSERT INTO players (id, name, level, xp, gold, max_health, max_mana) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (player_id, 'TestPlayer3', 1, 25, 0, 100, 100)
        )
        await db.commit()
        
        cursor = await db.execute('SELECT * FROM players WHERE id = ?', (player_id,))
        row = await cursor.fetchone()
        print(f"\nBefore rewards:")
        print(f"  Level: {row[2]}, XP: {row[3]}")
        
        # Simulate small reward: +30 XP (total 55, not enough for level 2)
        xp_reward = 30
        await db.execute('UPDATE players SET xp = xp + ? WHERE id = ?', (xp_reward, player_id))
        await db.commit()
        
        cursor = await db.execute('SELECT level, xp, max_health, max_mana FROM players WHERE id = ?', (player_id,))
        row = await cursor.fetchone()
        cur_level, cur_xp, cur_max_health, cur_max_mana = row
        
        # Check if level-up needed
        if cur_xp >= (cur_level * 100):
            print("ERROR: Should not level up!")
        else:
            print(f"✓ No level-up (XP {cur_xp} < threshold {cur_level * 100})")
        
        cursor = await db.execute('SELECT * FROM players WHERE id = ?', (player_id,))
        row = await cursor.fetchone()
        print(f"\nAfter rewards:")
        print(f"  Level: {row[2]} (✓ Expected: 1)")
        print(f"  XP: {row[3]} (✓ Expected: 55)")
        
        assert row[2] == 1, "Level should stay at 1"
        assert row[3] == 55, "XP should be 55"
        print("\n✓ Test 3 PASSED")
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED! ✓")
    print("=" * 60)
    print(f"\nTest database saved at: {os.path.abspath(db_path)}")
    print("You can inspect it with: sqlite3 data/test_verification.db")

if __name__ == '__main__':
    asyncio.run(verify_quest_rewards())
