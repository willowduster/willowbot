"""
Unit tests for quest reward claiming and level-up logic
"""
import unittest
import asyncio
import aiosqlite
import os
import tempfile
from unittest.mock import Mock, AsyncMock, MagicMock
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models.quest_manager import QuestManager
from src.models.quest import Quest, QuestReward, QuestType, QuestObjective, ObjectiveType


class TestQuestRewards(unittest.TestCase):
    """Test quest reward claiming and level-up mechanics"""
    
    def setUp(self):
        """Set up test database and quest manager"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Mock bot
        self.bot = Mock()
        self.bot.db_path = self.db_path
        
        async def mock_db_connect():
            return await aiosqlite.connect(self.db_path)
        
        self.bot.db_connect = mock_db_connect
        
        # Initialize database
        self.loop.run_until_complete(self._init_db())
        
        # Create quest manager with mock quest data
        self.quest_manager = QuestManager(self.bot)
        self.quest_manager.quests = {
            'test_quest_1': Quest(
                id='test_quest_1',
                title='Test Quest 1',
                description='A test quest',
                type=QuestType.COMBAT,
                objectives=[
                    QuestObjective(
                        type=ObjectiveType.COMBAT,
                        description='Defeat 1 enemy',
                        count=1
                    )
                ],
                rewards=QuestReward(
                    xp=150,  # Enough to level up from 1 to 2 (threshold is 100)
                    gold=50,
                    items=[]
                ),
                requirements={'level': 1},
                next_quest='test_quest_2'
            ),
            'test_quest_2': Quest(
                id='test_quest_2',
                title='Test Quest 2',
                description='Second test quest',
                type=QuestType.COMBAT,
                objectives=[
                    QuestObjective(
                        type=ObjectiveType.COMBAT,
                        description='Defeat 2 enemies',
                        count=2
                    )
                ],
                rewards=QuestReward(
                    xp=250,  # Enough to level up from 2 to 3 and have XP left over
                    gold=100,
                    items=[]
                ),
                requirements={'level': 2, 'previous_quest': 'test_quest_1'}
            )
        }
    
    async def _init_db(self):
        """Initialize test database schema"""
        async with await aiosqlite.connect(self.db_path) as db:
            # Create players table
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
            
            # Create active_quests table
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
            
            # Create inventory table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    player_id INTEGER,
                    item_id TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (player_id, item_id)
                )
            ''')
            
            await db.commit()
    
    def tearDown(self):
        """Clean up test database"""
        self.loop.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_reward_claim_single_level_up(self):
        """Test that claiming rewards with 150 XP levels player from 1 to 2"""
        async def run_test():
            # Create test player at level 1 with 0 XP
            async with await aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT INTO players (id, name, level, xp, gold) VALUES (?, ?, ?, ?, ?)',
                    (12345, 'TestPlayer', 1, 0, 0)
                )
                # Mark quest as completed but not claimed
                await db.execute(
                    'INSERT INTO active_quests (player_id, quest_id, objectives_progress, completed, rewards_claimed) VALUES (?, ?, ?, ?, ?)',
                    (12345, 'test_quest_1', '[1]', True, False)
                )
                await db.commit()
            
            # Claim rewards
            reward, old_level, new_level = await self.quest_manager.claim_quest_rewards(12345, 'test_quest_1')
            
            # Verify results
            self.assertIsNotNone(reward)
            self.assertEqual(old_level, 1)
            self.assertEqual(new_level, 2, "Player should level up from 1 to 2 with 150 XP")
            
            # Verify database state
            async with await aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('SELECT level, xp, gold, max_health, max_mana FROM players WHERE id = ?', (12345,))
                row = await cursor.fetchone()
                self.assertEqual(row[0], 2, "Level should be 2")
                self.assertEqual(row[1], 50, "XP should be 50 (150 - 100)")
                self.assertEqual(row[2], 50, "Gold should be 50")
                self.assertEqual(row[3], 110, "Max health should be 110 (100 + 10)")
                self.assertEqual(row[4], 105, "Max mana should be 105 (100 + 5)")
        
        self.loop.run_until_complete(run_test())
    
    def test_reward_claim_multi_level_up(self):
        """Test that claiming rewards with enough XP can trigger multiple level-ups"""
        async def run_test():
            # Create test player at level 1 with 50 XP
            async with await aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT INTO players (id, name, level, xp, gold) VALUES (?, ?, ?, ?, ?)',
                    (12346, 'TestPlayer2', 1, 50, 0)
                )
                # Mark a large XP quest as completed
                await db.execute(
                    'INSERT INTO active_quests (player_id, quest_id, objectives_progress, completed, rewards_claimed) VALUES (?, ?, ?, ?, ?)',
                    (12346, 'test_quest_2', '[2]', True, False)
                )
                await db.commit()
            
            # Claim rewards (250 XP + 50 existing = 300 total)
            # Should level: 1->2 (costs 100, left 200), 2->3 (costs 200, left 0)
            reward, old_level, new_level = await self.quest_manager.claim_quest_rewards(12346, 'test_quest_2')
            
            # Verify multi-level up
            self.assertIsNotNone(reward)
            self.assertEqual(old_level, 1)
            self.assertEqual(new_level, 3, "Player should level up from 1 to 3 with 300 total XP")
            
            # Verify database state
            async with await aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('SELECT level, xp, max_health, max_mana FROM players WHERE id = ?', (12346,))
                row = await cursor.fetchone()
                self.assertEqual(row[0], 3, "Level should be 3")
                self.assertEqual(row[1], 0, "XP should be 0 (300 - 100 - 200)")
                self.assertEqual(row[2], 120, "Max health should be 120 (100 + 10 + 10)")
                self.assertEqual(row[3], 110, "Max mana should be 110 (100 + 5 + 5)")
        
        self.loop.run_until_complete(run_test())
    
    def test_reward_claim_no_level_up(self):
        """Test that claiming small rewards doesn't level up player"""
        async def run_test():
            # Create test player at level 1 with 25 XP
            async with await aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT INTO players (id, name, level, xp, gold) VALUES (?, ?, ?, ?, ?)',
                    (12347, 'TestPlayer3', 1, 25, 0)
                )
                # Create a small XP quest
                small_quest = Quest(
                    id='small_quest',
                    title='Small Quest',
                    description='Small reward',
                    type=QuestType.COMBAT,
                    objectives=[QuestObjective(type=ObjectiveType.COMBAT, description='Test', count=1)],
                    rewards=QuestReward(xp=30, gold=10, items=[]),
                    requirements={'level': 1}
                )
                self.quest_manager.quests['small_quest'] = small_quest
                
                await db.execute(
                    'INSERT INTO active_quests (player_id, quest_id, objectives_progress, completed, rewards_claimed) VALUES (?, ?, ?, ?, ?)',
                    (12347, 'small_quest', '[1]', True, False)
                )
                await db.commit()
            
            # Claim rewards (30 XP + 25 existing = 55 total, not enough for level 2)
            reward, old_level, new_level = await self.quest_manager.claim_quest_rewards(12347, 'small_quest')
            
            # Verify no level-up
            self.assertIsNotNone(reward)
            self.assertEqual(old_level, 1)
            self.assertEqual(new_level, 1, "Player should stay at level 1 with only 55 XP")
            
            # Verify database state
            async with await aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('SELECT level, xp FROM players WHERE id = ?', (12347,))
                row = await cursor.fetchone()
                self.assertEqual(row[0], 1, "Level should still be 1")
                self.assertEqual(row[1], 55, "XP should be 55")
        
        self.loop.run_until_complete(run_test())
    
    def test_reward_claim_already_claimed(self):
        """Test that already claimed rewards return None"""
        async def run_test():
            async with await aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    'INSERT INTO players (id, name, level, xp) VALUES (?, ?, ?, ?)',
                    (12348, 'TestPlayer4', 1, 0)
                )
                # Quest already claimed
                await db.execute(
                    'INSERT INTO active_quests (player_id, quest_id, objectives_progress, completed, rewards_claimed) VALUES (?, ?, ?, ?, ?)',
                    (12348, 'test_quest_1', '[1]', True, True)
                )
                await db.commit()
            
            # Try to claim again
            reward, old_level, new_level = await self.quest_manager.claim_quest_rewards(12348, 'test_quest_1')
            
            # Should return None tuple
            self.assertIsNone(reward)
            self.assertEqual(old_level, 0)
            self.assertEqual(new_level, 0)
        
        self.loop.run_until_complete(run_test())


if __name__ == '__main__':
    unittest.main()
