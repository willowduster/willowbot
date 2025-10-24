import yaml
from pathlib import Path
import json
from typing import List, Dict, Optional, Tuple
from ..models.quest import (
    Quest, QuestChain, QuestObjective, QuestReward,
    PlayerQuest, QuestItem, Title, QuestType, ObjectiveType
)

class QuestManager:
    def __init__(self, bot):
        self.bot = bot
        self._load_quest_data()

    def _load_quest_data(self):
        """Load quest data from YAML files"""
        config_path = Path(__file__).parent.parent / 'config' / 'quests.yaml'
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
            
        # Parse quest chains
        self.quest_chains = {}
        self.quests = {}
        self.items = {}
        self.titles = {}

        # Load items
        for item_id, item_data in data['quest_items'].items():
            self.items[item_id] = QuestItem(
                id=item_id,
                name=item_data['name'],
                description=item_data['description'],
                effect=item_data['effect'],
                value=item_data['value']
            )

        # Load titles
        for title_id, title_data in data['titles'].items():
            self.titles[title_id] = Title(
                id=title_id,
                name=title_data['name'],
                description=title_data['description'],
                bonuses=title_data['bonuses']
            )

        # Load quest chains and quests
        for chain_data in data['quest_chains']:
            chain_quests = []
            for quest_data in chain_data['quests']:
                # Create quest objectives
                objectives = [
                    QuestObjective(
                        type=ObjectiveType(obj['type']),
                        description=obj['description'],
                        count=obj['count'],
                        enemy_type=obj.get('enemy_type'),
                        enemy_prefix=obj.get('enemy_prefix'),
                        enemy_suffix=obj.get('enemy_suffix'),
                        attack_type=obj.get('attack_type')
                    ) for obj in quest_data['objectives']
                ]

                # Create quest rewards
                rewards = QuestReward(
                    xp=quest_data['rewards']['xp'],
                    gold=quest_data['rewards']['gold'],
                    items=quest_data['rewards'].get('items', []),
                    title=quest_data['rewards'].get('title')
                )

                # Create quest
                quest = Quest(
                    id=quest_data['id'],
                    title=quest_data['title'],
                    description=quest_data['description'],
                    type=QuestType(quest_data['type']),
                    objectives=objectives,
                    rewards=rewards,
                    requirements=quest_data.get('requirements', {}),
                    next_quest=quest_data.get('next_quest')
                )
                
                chain_quests.append(quest)
                self.quests[quest.id] = quest

            # Create quest chain
            chain = QuestChain(
                id=chain_data['id'],
                name=chain_data['name'],
                description=chain_data['description'],
                quests=chain_quests,
                requirements=chain_data.get('requirements')
            )
            self.quest_chains[chain.id] = chain

    async def get_available_quests(self, player_id: int) -> List[Quest]:
        """Get all quests available to the player"""
        available_quests = []
        
        # Get player's level and completed quests
        async with self.bot.db.execute(
            'SELECT level FROM players WHERE id = ?', 
            (player_id,)
        ) as cursor:
            player_level = (await cursor.fetchone())[0]

        # Get completed quest chains
        async with self.bot.db.execute(
            'SELECT chain_id FROM completed_quest_chains WHERE player_id = ?',
            (player_id,)
        ) as cursor:
            completed_chains = set(row[0] for row in await cursor.fetchall())

        # Get active and completed quests
        async with self.bot.db.execute(
            'SELECT quest_id, completed FROM active_quests WHERE player_id = ?',
            (player_id,)
        ) as cursor:
            quest_status = {row[0]: row[1] for row in await cursor.fetchall()}

        for chain in self.quest_chains.values():
            # Check chain requirements
            if chain.requirements:
                if chain.requirements.get('level', 0) > player_level:
                    continue
                if chain.requirements.get('previous_chain') and \
                   chain.requirements['previous_chain'] not in completed_chains:
                    continue

            # Find the first incomplete quest in the chain
            for quest in chain.quests:
                if quest.id not in quest_status:
                    # Check quest requirements
                    meets_requirements = True
                    if quest.requirements:
                        if quest.requirements.get('level', 0) > player_level:
                            meets_requirements = False
                        if quest.requirements.get('previous_quest'):
                            prev_quest = quest.requirements['previous_quest']
                            if prev_quest not in quest_status or not quest_status[prev_quest]:
                                meets_requirements = False

                    if meets_requirements:
                        available_quests.append(quest)
                        break
                elif not quest_status[quest.id]:
                    available_quests.append(quest)
                    break

        return available_quests

    async def start_quest(self, player_id: int, quest_id: str) -> Optional[Quest]:
        """Start a quest for a player"""
        quest = self.quests.get(quest_id)
        if not quest:
            return None

        # Check if quest is already active
        async with self.bot.db.execute(
            'SELECT quest_id FROM active_quests WHERE player_id = ? AND quest_id = ?',
            (player_id, quest_id)
        ) as cursor:
            if await cursor.fetchone():
                return None

        # Initialize quest progress
        objectives_progress = json.dumps([0] * len(quest.objectives))
        await self.bot.db.execute('''
            INSERT INTO active_quests (player_id, quest_id, objectives_progress)
            VALUES (?, ?, ?)
        ''', (player_id, quest_id, objectives_progress))
        await self.bot.db.commit()

        return quest

    async def update_quest_progress(
        self, player_id: int, 
        enemy_type: Optional[str] = None,
        enemy_prefix: Optional[str] = None,
        enemy_suffix: Optional[str] = None,
        attack_type: Optional[str] = None
    ) -> List[Tuple[Quest, bool]]:  # Returns [(Quest, was_completed)]
        """Update quest progress after combat"""
        results = []
        
        # Get all active quests
        async with self.bot.db.execute(
            '''SELECT quest_id, objectives_progress 
               FROM active_quests 
               WHERE player_id = ? AND completed = FALSE''',
            (player_id,)
        ) as cursor:
            active_quests = await cursor.fetchall()

        for quest_id, objectives_progress in active_quests:
            quest = self.quests[quest_id]
            progress = json.loads(objectives_progress)
            was_completed = False
            updated = False

            # Check each objective
            for i, objective in enumerate(quest.objectives):
                if progress[i] >= objective.count:
                    continue

                matches = False
                if objective.type == ObjectiveType.COMBAT:
                    matches = (
                        (not objective.enemy_type or objective.enemy_type == enemy_type) and
                        (not objective.enemy_prefix or objective.enemy_prefix == enemy_prefix) and
                        (not objective.enemy_suffix or objective.enemy_suffix == enemy_suffix)
                    )
                elif objective.type == ObjectiveType.COMBAT_WITH_ATTACK:
                    matches = (
                        (not objective.enemy_type or objective.enemy_type == enemy_type) and
                        objective.attack_type == attack_type
                    )

                if matches:
                    progress[i] += 1
                    updated = True

            if updated:
                # Check if quest is now complete
                is_complete = all(progress[i] >= obj.count for i, obj in enumerate(quest.objectives))
                
                # Update database
                await self.bot.db.execute('''
                    UPDATE active_quests 
                    SET objectives_progress = ?, completed = ?
                    WHERE player_id = ? AND quest_id = ?
                ''', (json.dumps(progress), is_complete, player_id, quest_id))
                
                results.append((quest, is_complete))
                was_completed = is_complete

            if was_completed:
                # If this completes a chain, record it
                for chain in self.quest_chains.values():
                    if quest_id == chain.quests[-1].id:
                        await self.bot.db.execute('''
                            INSERT OR IGNORE INTO completed_quest_chains (player_id, chain_id)
                            VALUES (?, ?)
                        ''', (player_id, chain.id))

        await self.bot.db.commit()
        return results

    async def claim_quest_rewards(self, player_id: int, quest_id: str) -> Optional[QuestReward]:
        """Claim rewards for a completed quest"""
        # Check if quest is completed and rewards aren't claimed
        async with self.bot.db.execute(
            '''SELECT completed, rewards_claimed 
               FROM active_quests 
               WHERE player_id = ? AND quest_id = ?''',
            (player_id, quest_id)
        ) as cursor:
            result = await cursor.fetchone()
            if not result or not result[0] or result[1]:
                return None

        quest = self.quests[quest_id]
        
        # Update player stats
        await self.bot.db.execute('''
            UPDATE players 
            SET xp = xp + ?, gold = gold + ?
            WHERE id = ?
        ''', (quest.rewards.xp, quest.rewards.gold, player_id))

        # Add items to inventory
        for item in quest.rewards.items:
            await self.bot.db.execute('''
                INSERT INTO inventory (player_id, item_id, count)
                VALUES (?, ?, ?)
                ON CONFLICT(player_id, item_id) DO UPDATE SET
                count = count + ?
            ''', (player_id, item['id'], item['count'], item['count']))

        # Add title if any
        if quest.rewards.title:
            await self.bot.db.execute('''
                INSERT OR IGNORE INTO player_titles (player_id, title_id)
                VALUES (?, ?)
            ''', (player_id, quest.rewards.title))

        # Mark rewards as claimed
        await self.bot.db.execute('''
            UPDATE active_quests 
            SET rewards_claimed = TRUE
            WHERE player_id = ? AND quest_id = ?
        ''', (player_id, quest_id))

        await self.bot.db.commit()
        return quest.rewards