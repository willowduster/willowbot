import yaml
from pathlib import Path
import json
import logging
from typing import List, Dict, Optional, Tuple
from ..models.quest import (
    Quest, QuestChain, QuestObjective, QuestReward,
    PlayerQuest, QuestItem, Title, QuestType, ObjectiveType
)

logger = logging.getLogger('willowbot.quest_manager')

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

        # Load items (optional - may not exist in all quest configs)
        if 'quest_items' in data:
            for item_id, item_data in data['quest_items'].items():
                self.items[item_id] = QuestItem(
                    id=item_id,
                    name=item_data['name'],
                    description=item_data['description'],
                effect=item_data['effect'],
                value=item_data['value']
            )

        # Load titles (optional section)
        if 'titles' in data:
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
        
        # Get player's level and create player if they don't exist
        async with await self.bot.db_connect() as db:
            async with db.execute(
                'SELECT level FROM players WHERE id = ?', 
                (player_id,)
            ) as cursor:
                result = await cursor.fetchone()
                if result is None:
                    # Get player's name from Discord
                    guild = self.bot.guilds[0]  # Get first guild bot is in
                    member = await guild.fetch_member(player_id)
                    name = member.display_name if member else str(player_id)

                    # Create new player
                    await db.execute('''
                        INSERT INTO players (id, name, level, xp, health, max_health, mana, max_mana)
                        VALUES (?, ?, 1, 0, 100, 100, 100, 100)
                    ''', (player_id, name))
                    await db.commit()
                    player_level = 1
                else:
                    player_level = result[0]
                
            # Get completed quest chains
            async with db.execute(
                'SELECT chain_id FROM completed_quest_chains WHERE player_id = ?',
                (player_id,)
            ) as cursor:
                completed_chains = set(row[0] for row in await cursor.fetchall())

            # Get active and completed quests with rewards claimed status
            async with db.execute(
                'SELECT quest_id, completed, rewards_claimed FROM active_quests WHERE player_id = ?',
                (player_id,)
            ) as cursor:
                quest_data = await cursor.fetchall()
                # Store quest status: {quest_id: (completed, rewards_claimed)}
                quest_status = {row[0]: (row[1], row[2]) for row in quest_data}



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
                    # Quest never started - check requirements
                    meets_requirements = True
                    if quest.requirements:
                        if quest.requirements.get('level', 0) > player_level:
                            meets_requirements = False
                        if quest.requirements.get('previous_quest'):
                            prev_quest = quest.requirements['previous_quest']
                            # Previous quest must be completed with rewards claimed
                            if prev_quest not in quest_status or not quest_status[prev_quest][0] or not quest_status[prev_quest][1]:
                                meets_requirements = False

                    if meets_requirements:
                        available_quests.append(quest)
                        break
                else:
                    # Quest exists in active_quests - check if it's still in progress
                    completed, rewards_claimed = quest_status[quest.id]
                    if completed and rewards_claimed:
                        # Quest is fully completed - skip to next quest in chain
                        continue
                    elif completed and not rewards_claimed:
                        # Quest is completed but rewards not claimed - skip it for now
                        # (they should use another command to claim rewards)
                        continue
                    else:
                        # Quest is incomplete - it's available to continue
                        available_quests.append(quest)
                        break

        return available_quests

    async def start_quest(self, player_id: int, quest_id: str) -> Optional[Quest]:
        """Start a quest for a player"""
        quest = self.quests.get(quest_id)
        if not quest:
            return None

        # Check if quest is already active
        async with await self.bot.db_connect() as db:
            async with db.execute(
                'SELECT objectives_progress FROM active_quests WHERE player_id = ? AND quest_id = ?',
                (player_id, quest_id)
            ) as cursor:
                if row := await cursor.fetchone():
                    # Quest is already active
                    quest.objectives_progress = json.loads(row[0])
                    return quest

            # Initialize quest progress
            objectives_progress = json.dumps([0] * len(quest.objectives))
            await db.execute('''
                INSERT INTO active_quests (player_id, quest_id, objectives_progress)
                VALUES (?, ?, ?)
            ''', (player_id, quest_id, objectives_progress))
            await db.commit()

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
        async with await self.bot.db_connect() as db:
            async with db.execute(
                '''SELECT quest_id, objectives_progress 
                   FROM active_quests 
                   WHERE player_id = ? AND completed = FALSE''',
                (player_id,)
            ) as cursor:
                active_quests = await cursor.fetchall()

        for quest_id, objectives_progress in active_quests:
            # Check if quest still exists in config
            if quest_id not in self.quests:
                logger.warning(f"Quest {quest_id} not found in config, skipping. Consider cleaning up database.")
                continue
                
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
                async with await self.bot.db_connect() as db:
                    await db.execute('''
                        UPDATE active_quests 
                        SET objectives_progress = ?, completed = ?
                        WHERE player_id = ? AND quest_id = ?
                    ''', (json.dumps(progress), is_complete, player_id, quest_id))
                    await db.commit()
                
                results.append((quest, is_complete))
                was_completed = is_complete

            if was_completed:
                # Auto-claim rewards when quest is completed
                await self.claim_quest_rewards(player_id, quest_id)
                logger.info(f"Auto-claimed rewards for quest {quest_id} for player {player_id}")
                
                # If this completes a chain, record it
                async with await self.bot.db_connect() as db:
                    for chain in self.quest_chains.values():
                        if quest_id == chain.quests[-1].id:
                            await db.execute('''
                                INSERT OR IGNORE INTO completed_quest_chains (player_id, chain_id)
                                VALUES (?, ?)
                            ''', (player_id, chain.id))
                    await db.commit()
                
                # Auto-start next quest in chain if it exists
                if quest.next_quest:
                    next_quest_id = quest.next_quest
                    # Check if the next quest is available and not already active
                    async with await self.bot.db_connect() as db:
                        async with db.execute(
                            'SELECT 1 FROM active_quests WHERE player_id = ? AND quest_id = ?',
                            (player_id, next_quest_id)
                        ) as cursor:
                            already_active = await cursor.fetchone()
                        
                        if not already_active and next_quest_id in self.quests:
                            next_quest = self.quests[next_quest_id]
                            
                            # Get player level for requirement checking
                            async with db.execute(
                                'SELECT level FROM players WHERE id = ?',
                                (player_id,)
                            ) as cursor:
                                player_row = await cursor.fetchone()
                                player_level = player_row[0] if player_row else 1
                            
                            # Check if player meets requirements (level only - previous quest is already complete)
                            can_start = True
                            if next_quest.requirements:
                                if next_quest.requirements.get('level', 0) > player_level:
                                    can_start = False
                            
                            if can_start:
                                # Start the next quest automatically
                                await self.start_quest(player_id, next_quest_id)
                                logger.info(f"Auto-started next quest {next_quest_id} for player {player_id}")

        return results

    async def claim_quest_rewards(self, player_id: int, quest_id: str) -> Optional[QuestReward]:
        """Claim rewards for a completed quest"""
        # Check if quest is completed and rewards aren't claimed
        async with await self.bot.db_connect() as db:
            async with db.execute(
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
            await db.execute('''
                UPDATE players 
                SET xp = xp + ?, gold = gold + ?
                WHERE id = ?
            ''', (quest.rewards.xp, quest.rewards.gold, player_id))

            # Add items to inventory
            for item in quest.rewards.items:
                await db.execute('''
                    INSERT INTO inventory (player_id, item_id, count)
                    VALUES (?, ?, ?)
                    ON CONFLICT(player_id, item_id) DO UPDATE SET
                    count = count + ?
                ''', (player_id, item['id'], item['count'], item['count']))

            # Add title if any
            if quest.rewards.title:
                await db.execute('''
                    INSERT OR IGNORE INTO player_titles (player_id, title_id)
                    VALUES (?, ?)
                ''', (player_id, quest.rewards.title))

            # Mark quest as completed and rewards claimed (keep it in active_quests for quest chain tracking)
            await db.execute('''
                UPDATE active_quests 
                SET completed = 1, rewards_claimed = 1
                WHERE player_id = ? AND quest_id = ?
            ''', (player_id, quest_id))

            await db.commit()
            logger.info(f"Claimed rewards and marked quest {quest_id} as completed for player {player_id}")
            return quest.rewards