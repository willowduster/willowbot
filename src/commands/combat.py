import discord
import logging
import asyncio
from discord.ext import commands
from ..models.player import Player
from ..models.enemy import EnemyGenerator
from ..models.combat import Attack, CombatEntity
from ..models.inventory_manager import InventoryManager
from ..models.quest_manager import QuestManager
from ..models.inventory import ItemType
from ..models.quest import QuestType, ObjectiveType
import random

logger = logging.getLogger('willowbot.combat')

class CombatCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.enemy_generator = EnemyGenerator()
        self.inventory_manager = InventoryManager(bot)
        self.quest_manager = QuestManager(bot)
        # Track active combat sessions
        self.active_combats = {}
        # Track victory messages for post-combat actions
        self.victory_messages = {}
        # Reaction emojis for combat actions
        self.MELEE_EMOJI = "⚔️"
        self.MAGIC_EMOJI = "🔮"
        self.FLEE_EMOJI = "🏃"
        self.ITEM_EMOJI = "🧪"
        self.PRAY_EMOJI = "🙏"
        self.EQUIPMENT_EMOJI = "🛡️"
        self.combat_emojis = [self.MELEE_EMOJI, self.MAGIC_EMOJI, self.ITEM_EMOJI, self.FLEE_EMOJI]
        # Defeat reaction emojis
        self.RESTART_EMOJI = "🔄"  # Heal and restart quest
        self.LEAVE_EMOJI = "🚪"    # Leave battle and view status
        self.defeat_emojis = [self.RESTART_EMOJI, self.LEAVE_EMOJI]
        logger.info("Combat Commands initialized with emojis: %s", self.combat_emojis)
    
    def generate_loot(self, enemy: CombatEntity) -> list:
        """Generate random loot drops based on enemy level"""
        loot = []
        
        # Equipment loot pools by level (using correct item IDs from items.yaml)
        # Level 1-3: Basic equipment
        basic_equipment = ['weapon_1', 'helmet_1', 'armor_1', 'pants_1', 'boots_1']  # Rusty Sword, Leather Cap, etc.
        # Level 3-6: Common equipment
        common_equipment = ['weapon_2', 'weapon_3', 'helmet_2', 'armor_2', 'armor_3', 'pants_2', 'boots_2']
        # Level 5+: Uncommon equipment
        uncommon_equipment = ['weapon_4', 'weapon_5', 'helmet_3', 'helmet_4', 'armor_4', 'pants_3', 'boots_3']
        
        # Consumables by tier (using correct item IDs)
        basic_consumables = ['consumable_1', 'consumable_2']  # Health Potion, Mana Potion
        advanced_consumables = ['consumable_3', 'consumable_4']  # Greater Health/Mana Potions
        
        # Gold always drops
        gold_amount = random.randint(15 * enemy.level, 30 * enemy.level)
        
        # GUARANTEED: 1 piece of equipment always drops
        # Choose equipment tier based on enemy level
        if enemy.level <= 3:
            item_id = random.choice(basic_equipment)
        elif enemy.level <= 6:
            # 60% common, 40% basic
            if random.random() < 0.6:
                item_id = random.choice(common_equipment)
            else:
                item_id = random.choice(basic_equipment)
        else:
            # 50% uncommon, 35% common, 15% basic
            roll = random.random()
            if roll < 0.5:
                item_id = random.choice(uncommon_equipment)
            elif roll < 0.85:
                item_id = random.choice(common_equipment)
            else:
                item_id = random.choice(basic_equipment)
        
        loot.append((item_id, 1))
        
        # GUARANTEED: 1 consumable always drops (health or mana potion)
        # Choose consumable based on enemy level
        if enemy.level >= 5 and random.random() < 0.5:
            # 50% chance for advanced consumable at level 5+
            consumable = random.choice(advanced_consumables)
        else:
            consumable = random.choice(basic_consumables)
        
        loot.append((consumable, 1))
        
        # BONUS: 30% chance for additional consumable
        if random.random() < 0.3:
            if enemy.level >= 5:
                bonus_consumable = random.choice(basic_consumables + advanced_consumables)
            else:
                bonus_consumable = random.choice(basic_consumables)
            loot.append((bonus_consumable, 1))
        
        return loot, gold_amount
        
    async def start_quest_combat(self, channel, user_id: int, enemy_type: str = None):
        """Start combat as part of a quest"""
        logger.info(f"Starting quest combat for user {user_id} with enemy type {enemy_type}")
        
        # First check if user is already in combat
        if user_id in self.active_combats:
            logger.warning(f"User {user_id} is already in combat, clearing existing state")
            del self.active_combats[user_id]
        
        async with await self.bot.db_connect() as db:
            # Reset any existing combat state in database
            await db.execute('''
                UPDATE players 
                SET in_combat = FALSE, current_enemy = NULL
                WHERE id = ?
            ''', (user_id,))
            await db.commit()
            
            cursor = await db.execute('SELECT * FROM players WHERE id = ?', (user_id,))
            player_data = await cursor.fetchone()
            
            if not player_data:
                logger.error(f"No player data found for user {user_id}")
                await channel.send("Error: Player data not found. Please try again.")
                return
                
            # Create player object
            player = Player(
                id=player_data[0],
                name=player_data[1],
                level=player_data[2],
                xp=player_data[3],
                health=player_data[4],
                max_health=player_data[5],
                mana=player_data[6],
                max_mana=player_data[7]
            )

            # Verify player health
            if player.health <= 0:
                logger.info(f"Restoring health for player {user_id} before combat")
                player.health = player.max_health // 2  # Restore 50% health
                await db.execute('UPDATE players SET health = ? WHERE id = ?', (player.health, user_id))
                await db.commit()
            logger.info(f"Created player object for {player.name} (Level {player.level})")
            
            # Generate enemy based on player level
            enemy = self.enemy_generator.generate_enemy(player.level)
            logger.info(f"Generated enemy: {enemy.name} (Level {enemy.level})")
            
            # Get healing item count
            healing_item_count = await self.get_healing_consumable_count(user_id)
            
            # Get equipment bonuses
            equipment = await self.inventory_manager.get_equipment(user_id)
            equipment_stats = equipment.get_total_stats() if equipment else {}
            
            # Initialize combat
            init_embed = discord.Embed(
                title="⚔️ Combat Started!",
                description=f"You are fighting a level {enemy.level} {enemy.name}!",
                color=discord.Color.red()
            )
            
            # Build player stats with equipment bonuses
            player_stats_text = f"Health: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}"
            if equipment_stats:
                bonus_parts = []
                if equipment_stats.get('damage', 0) > 0:
                    bonus_parts.append(f"⚔️ +{equipment_stats['damage']} Attack")
                if equipment_stats.get('magic_damage', 0) > 0:
                    bonus_parts.append(f"🔮 +{equipment_stats['magic_damage']} Magic")
                if equipment_stats.get('defense', 0) > 0:
                    bonus_parts.append(f"🛡️ +{equipment_stats['defense']} Defense")
                if equipment_stats.get('magic_defense', 0) > 0:
                    bonus_parts.append(f"✨ +{equipment_stats['magic_defense']} Magic Def")
                if equipment_stats.get('crit_chance', 0) > 0:
                    bonus_parts.append(f"💥 +{equipment_stats['crit_chance']}% Crit")
                if bonus_parts:
                    player_stats_text += "\n" + " | ".join(bonus_parts)
            
            init_embed.add_field(
                name="Your Stats", 
                value=player_stats_text,
                inline=True
            )
            init_embed.add_field(
                name="Enemy Stats", 
                value=f"Health: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}",
                inline=True
            )
            
            actions_text = f"{self.MELEE_EMOJI} Melee Attack\n{self.MAGIC_EMOJI} Magic Attack\n{self.ITEM_EMOJI} Use Item"
            if healing_item_count > 0:
                actions_text += f" ({healing_item_count} healing items)"
            
            # Always show pray option
            actions_text += f"\n{self.PRAY_EMOJI} Pray (restore mana)"
            actions_text += f"\n{self.FLEE_EMOJI} Flee"
            
            init_embed.add_field(
                name="Actions",
                value=actions_text,
                inline=False
            )
            
            combat_msg = await channel.send(embed=init_embed)
            logger.info("Sent combat initialization message")
            
            # Store combat session IMMEDIATELY before adding reactions
            # This prevents race condition where user clicks before session is stored
            self.active_combats[user_id] = {
                'message_id': combat_msg.id,
                'player': player,
                'enemy': enemy,
                'turn_history': [],  # Track all combat turns
            }
            logger.info(f"Stored combat session for user {user_id}")
            
            # Add combat action reactions AFTER storing the session
            for emoji in self.combat_emojis:
                await combat_msg.add_reaction(emoji)
            
            # Always add pray emoji
            await combat_msg.add_reaction(self.PRAY_EMOJI)
            
            logger.info("Added combat reaction emojis")
            
            # Update player state in database
            await db.execute('''
                UPDATE players 
                SET in_combat = TRUE, current_enemy = ?
                WHERE id = ?
            ''', (enemy.name, user_id))
            await db.commit()
            logger.info(f"Updated player combat state in database for user {user_id}")
            
            
        return combat_msg
    
    async def handle_combat_round(self, channel, user_id: int, attack_type: str):
        """Handle a round of combat"""
        combat_data = self.active_combats.get(user_id)
        if not combat_data:
            return
            
        player = combat_data['player']
        enemy = combat_data['enemy']
        message_id = combat_data['message_id']
        turn_history = combat_data.get('turn_history', [])
        
        # Get the combat message to edit
        try:
            combat_msg = await channel.fetch_message(message_id)
        except:
            await channel.send("Combat message not found!")
            return
        
        # Get the appropriate attack
        attack = next((a for a in player.basic_attacks if a.attack_type == attack_type), None)
        if not attack:
            # Update message showing error
            error_text = f"❌ No {attack_type} attack available!"
            turn_history.append(error_text)
            
            # Build history display
            history_display = "\n".join(turn_history[-10:])  # Show last 10 turns
            
            error_embed = discord.Embed(
                title="⚔️ Combat",
                description=f"**Combat History:**\n{history_display}",
                color=discord.Color.red()
            )
            error_embed.add_field(name="Your Stats", value=f"Health: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}", inline=True)
            error_embed.add_field(name="Enemy Stats", value=f"Health: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}", inline=True)
            await combat_msg.edit(embed=error_embed)
            # Clear and re-add reactions
            await combat_msg.clear_reactions()
            for emoji in self.combat_emojis:
                await combat_msg.add_reaction(emoji)
            return
        
        # Process player's attack
        logger.info(f"Before attack - Enemy HP: {enemy.health}/{enemy.max_health}, Enemy Mana: {enemy.mana}/{enemy.max_mana}")
        logger.info(f"Before attack - Player HP: {player.health}/{player.max_health}, Player Mana: {player.mana}/{player.max_mana}")
        result = attack.execute(player, enemy)
        logger.info(f"After attack - Enemy HP: {enemy.health}/{enemy.max_health}, Enemy Mana: {enemy.max_mana}")
        logger.info(f"After attack - Player HP: {player.health}/{player.max_health}, Player Mana: {player.mana}/{player.max_mana}")
        logger.info(f"Attack result: {result}")
        
        # Add player's turn to history
        if result['success']:
            turn_history.append(f"⚔️ You used {attack.name} - {result['damage']} damage!")
        else:
            turn_history.append(f"⚔️ You tried {attack.name} - {result['message']}")
        
        # Build history display
        history_display = "\n".join(turn_history[-10:])  # Show last 10 turns
        
        player_embed = discord.Embed(
            title="⚔️ Combat - Your Attack",
            description=f"**Combat History:**\n{history_display}",
            color=discord.Color.blue()
        )
        player_embed.add_field(name="Your Stats", value=f"HP: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}", inline=True)
        player_embed.add_field(name="Enemy Stats", value=f"HP: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}", inline=True)
        await combat_msg.edit(embed=player_embed)
        await combat_msg.clear_reactions()
        
        # Check if enemy is defeated
        if not enemy.is_alive():
            # Record the kill
            async with await self.bot.db_connect() as db:
                await db.execute('''
                    INSERT INTO player_kills (player_id, enemy_name, enemy_level)
                    VALUES (?, ?, ?)
                ''', (user_id, enemy.name, enemy.level))
                await db.commit()
            
            # Update quest progress
            # Parse enemy name to get type/prefix/suffix
            enemy_name_parts = enemy.name.split()
            enemy_type = None
            enemy_prefix = None
            enemy_suffix = None
            
            # Try to identify enemy parts from the name
            # This is a simple heuristic - could be improved
            if len(enemy_name_parts) == 1:
                enemy_type = enemy_name_parts[0]
            elif len(enemy_name_parts) >= 2:
                # Check if last part is "of Something" (suffix)
                if "of" in enemy.name:
                    of_index = enemy_name_parts.index("of")
                    enemy_prefix = enemy_name_parts[0] if of_index > 0 else None
                    enemy_type = " ".join(enemy_name_parts[1:of_index]) if of_index > 1 else enemy_name_parts[of_index - 1]
                    enemy_suffix = " ".join(enemy_name_parts[of_index:]) if of_index < len(enemy_name_parts) - 1 else None
                else:
                    # Assume first word is prefix, rest is type
                    enemy_prefix = enemy_name_parts[0]
                    enemy_type = " ".join(enemy_name_parts[1:])
            
            # Update quest progress for combat
            quest_results = await self.quest_manager.update_quest_progress(
                user_id,
                enemy_type=enemy_type,
                enemy_prefix=enemy_prefix,
                enemy_suffix=enemy_suffix
            )
            
            # Calculate rewards
            xp_gained = 50 + (enemy.level * 10)
            loot_items, gold_dropped = self.generate_loot(enemy)
            player.xp += xp_gained
            
            # Check for level up
            leveled_up = player.xp >= player.xp_needed_for_next_level()
            old_level = player.level
            if leveled_up:
                player.level_up()
            
            # Add loot to inventory
            added_items = []
            failed_items = []
            if loot_items:
                # Convert item IDs to Item objects
                items_to_add = []
                for item_id, count in loot_items:
                    item = self.inventory_manager.items.get(item_id)
                    if item:
                        items_to_add.append((item, count))
                
                if items_to_add:
                    added_items, failed_items = await self.inventory_manager.add_items(user_id, items_to_add)
            
            # Auto-equip better gear from inventory
            await self.inventory_manager.auto_equip_better_gear(user_id)
            
            # Refresh player stats after equipment changes
            equipment = await self.inventory_manager.get_equipment(user_id)
            await self.inventory_manager.update_player_stats(user_id, equipment)
            
            # Create victory message
            victory_embed = discord.Embed(
                title="🎉 Victory!",
                description=f"You defeated {enemy.name}!",
                color=discord.Color.gold()
            )
            
            # XP and Level
            xp_text = f"**+{xp_gained} XP**"
            if leveled_up:
                xp_text += f"\n🎉 **Level Up!** {old_level} → {player.level}"
            victory_embed.add_field(
                name="Experience",
                value=xp_text,
                inline=False
            )
            
            # Gold
            victory_embed.add_field(
                name="💰 Gold",
                value=f"+{gold_dropped} gold",
                inline=True
            )
            
            # Loot
            if added_items:
                loot_text = "\n".join([f"• {item.name} x{count}" for item, count in added_items])
                victory_embed.add_field(
                    name="🎁 Loot",
                    value=loot_text,
                    inline=True
                )
            
            if failed_items:
                failed_text = "\n".join([f"• {item.name} x{count}" for item, count in failed_items])
                victory_embed.add_field(
                    name="⚠️ Inventory Full",
                    value=f"Could not add:\n{failed_text}",
                    inline=False
                )
            
            # Show quest progress/completion
            if quest_results:
                quest_text = []
                for quest, was_completed in quest_results:
                    if was_completed:
                        quest_text.append(f"✅ **{quest.title}** - COMPLETED!")
                    else:
                        # Get current progress
                        async with await self.bot.db_connect() as db:
                            cursor = await db.execute(
                                'SELECT objectives_progress FROM active_quests WHERE player_id = ? AND quest_id = ?',
                                (user_id, quest.id)
                            )
                            row = await cursor.fetchone()
                            if row:
                                import json
                                progress = json.loads(row[0])
                                # Show first incomplete objective
                                for i, obj in enumerate(quest.objectives):
                                    if progress[i] < obj.count:
                                        quest_text.append(f"📜 **{quest.title}**: {progress[i]}/{obj.count} {obj.description}")
                                        break
                
                if quest_text:
                    victory_embed.add_field(
                        name="📋 Quest Progress",
                        value="\n".join(quest_text),
                        inline=False
                    )
            
            # Get updated player stats
            async with await self.bot.db_connect() as db:
                # Update gold
                await db.execute('''
                    UPDATE players 
                    SET gold = gold + ?
                    WHERE id = ?
                ''', (gold_dropped, user_id))
                
                # Update player stats (including max_health and max_mana if leveled up)
                await db.execute('''
                    UPDATE players 
                    SET health = ?, mana = ?, xp = ?, level = ?, 
                        max_health = ?, max_mana = ?,
                        in_combat = FALSE, current_enemy = NULL
                    WHERE id = ?
                ''', (player.health, player.mana, player.xp, player.level, 
                      player.max_health, player.max_mana, player.id))
                
                # Get updated stats for display including deaths and kills
                cursor = await db.execute('''
                    SELECT level, health, max_health, mana, max_mana, xp, gold, deaths,
                           damage_bonus, magic_damage_bonus, defense, magic_defense, 
                           crit_chance_bonus
                    FROM players WHERE id = ?
                ''', (user_id,))
                stats = await cursor.fetchone()
                
                cursor = await db.execute('''
                    SELECT COUNT(*) FROM player_kills WHERE player_id = ?
                ''', (user_id,))
                kills_row = await cursor.fetchone()
                kills = kills_row[0] if kills_row else 0
                
                await db.commit()
            
            # Add stats footer
            if stats:
                level, hp, max_hp, mana, max_mana, xp, gold, deaths, damage_bonus, magic_damage_bonus, defense, magic_defense, crit_chance_bonus = stats
                xp_needed = level * 100
                
                # Format combat stats
                combat_stats = f"⚔️ Damage: +{damage_bonus} | 🔮 Magic: +{magic_damage_bonus}\n"
                combat_stats += f"🛡️ Defense: {defense} | 🌟 Magic Def: {magic_defense}\n"
                combat_stats += f"💥 Crit Chance: +{crit_chance_bonus:.1f}%"
                
                victory_embed.add_field(
                    name="📊 Your Stats",
                    value=f"**Level {level}**\n"
                          f"HP: {hp}/{max_hp} | Mana: {mana}/{max_mana}\n"
                          f"XP: {xp}/{xp_needed} | Gold: {gold}\n"
                          f"{combat_stats}\n"
                          f"💀 Deaths: {deaths} | ⚔️ Kills: {kills}",
                    inline=False
                )
            
            # Add action options footer
            victory_embed.add_field(
                name="⚙️ Actions",
                value="🛏️ Rest\n▶️ Next Quest\n🎒 Inventory\n📊 Stats\n🛡️ Equipment",
                inline=False
            )
            
            victory_msg = await channel.send(embed=victory_embed)
            
            # Add reaction options
            await victory_msg.add_reaction("🛏️")  # Rest to restore HP/Mana
            await victory_msg.add_reaction("▶️")  # Next quest
            await victory_msg.add_reaction("🎒")  # Inventory
            await victory_msg.add_reaction("📊")  # Stats
            await victory_msg.add_reaction("🛡️")  # Equipment
            
            # Store victory message for reaction handling
            self.victory_messages[user_id] = {
                'message_id': victory_msg.id,
                'channel_id': channel.id
            }
            
            # Clean up combat
            del self.active_combats[user_id]
            return
        
        # Enemy's turn - AI decision making
        await asyncio.sleep(0.5)
        
        # Determine enemy action based on health percentage
        health_percent = enemy.health / enemy.max_health
        action_roll = random.random()
        
        if health_percent < 0.3:
            # Low health: 60% heal, 30% attack, 10% flee
            if action_roll < 0.6:
                action = "heal"
            elif action_roll < 0.9:
                action = "attack"
            else:
                action = "flee"
        elif health_percent < 0.6:
            # Medium health: 70% attack, 20% heal, 10% flee
            if action_roll < 0.7:
                action = "attack"
            elif action_roll < 0.9:
                action = "heal"
            else:
                action = "flee"
        else:
            # High health: 85% attack, 10% heal, 5% flee
            if action_roll < 0.85:
                action = "attack"
            elif action_roll < 0.95:
                action = "heal"
            else:
                action = "flee"
        
        # Enemy regenerates mana to sustain the fight
        if enemy.mana < enemy.max_mana:
            mana_regen = int(enemy.max_mana * 0.3)  # 30% mana regeneration per turn
            enemy.mana = min(enemy.max_mana, enemy.mana + mana_regen)
        
        if action == "flee":
            # Enemy attempts to flee
            flee_chance = 0.15  # 15% base flee chance
            if random.random() < flee_chance:
                turn_history.append(f"🏃 {enemy.name} fled from battle!")
                
                # Build history display
                history_display = "\n".join(turn_history[-10:])
                
                enemy_embed = discord.Embed(
                    title="Enemy Fled!",
                    description=f"**Combat History:**\n{history_display}",
                    color=discord.Color.orange()
                )
                await combat_msg.edit(embed=enemy_embed)
                
                # Treat as player victory - enemy fled = player wins
                # Set enemy health to 0 to trigger victory sequence
                enemy.health = 0
                
                # Update quest progress
                enemy_name_parts = enemy.name.split()
                enemy_type = None
                enemy_prefix = None
                enemy_suffix = None
                
                if len(enemy_name_parts) == 1:
                    enemy_type = enemy_name_parts[0]
                elif len(enemy_name_parts) >= 2:
                    if "of" in enemy.name:
                        of_index = enemy_name_parts.index("of")
                        enemy_prefix = enemy_name_parts[0] if of_index > 0 else None
                        enemy_type = " ".join(enemy_name_parts[1:of_index]) if of_index > 1 else enemy_name_parts[of_index - 1]
                        enemy_suffix = " ".join(enemy_name_parts[of_index:]) if of_index < len(enemy_name_parts) - 1 else None
                    else:
                        enemy_prefix = enemy_name_parts[0]
                        enemy_type = " ".join(enemy_name_parts[1:])
                
                quest_results = await self.quest_manager.update_quest_progress(
                    user_id,
                    enemy_type=enemy_type,
                    enemy_prefix=enemy_prefix,
                    enemy_suffix=enemy_suffix
                )
                
                # Calculate rewards
                xp_gained = 50 + (enemy.level * 10)
                loot_items, gold_dropped = self.generate_loot(enemy)
                player.xp += xp_gained
                
                # Check for level up
                leveled_up = player.xp >= player.xp_needed_for_next_level()
                old_level = player.level
                if leveled_up:
                    player.level_up()
                
                # Add loot to inventory
                added_items = []
                failed_items = []
                if loot_items:
                    items_to_add = []
                    for item_id, count in loot_items:
                        item = self.inventory_manager.items.get(item_id)
                        if item:
                            items_to_add.append((item, count))
                    
                    if items_to_add:
                        added_items, failed_items = await self.inventory_manager.add_items(user_id, items_to_add)
                
                # Auto-equip better gear from inventory
                await self.inventory_manager.auto_equip_better_gear(user_id)
                
                # Refresh player stats after equipment changes
                equipment = await self.inventory_manager.get_equipment(user_id)
                await self.inventory_manager.update_player_stats(user_id, equipment)
                
                # Create victory message
                victory_embed = discord.Embed(
                    title="🎉 Victory!",
                    description=f"The {enemy.name} fled from your might!",
                    color=discord.Color.gold()
                )
                
                # XP and Level
                xp_text = f"**+{xp_gained} XP**"
                if leveled_up:
                    xp_text += f"\n🎉 **Level Up!** {old_level} → {player.level}"
                victory_embed.add_field(
                    name="Experience",
                    value=xp_text,
                    inline=False
                )
                
                # Gold
                victory_embed.add_field(
                    name="💰 Gold",
                    value=f"+{gold_dropped} gold",
                    inline=True
                )
                
                # Loot
                if added_items:
                    loot_text = "\n".join([f"• {item.name} x{count}" for item, count in added_items])
                    victory_embed.add_field(
                        name="🎁 Loot",
                        value=loot_text,
                        inline=True
                    )
                
                if failed_items:
                    failed_text = "\n".join([f"• {item.name} x{count}" for item, count in failed_items])
                    victory_embed.add_field(
                        name="⚠️ Inventory Full",
                        value=f"Could not add:\n{failed_text}",
                        inline=False
                    )
                
                # Show quest progress/completion
                if quest_results:
                    quest_text = []
                    for quest, was_completed in quest_results:
                        if was_completed:
                            quest_text.append(f"✅ **{quest.title}** - COMPLETED!")
                        else:
                            async with await self.bot.db_connect() as db:
                                cursor = await db.execute(
                                    'SELECT objectives_progress FROM active_quests WHERE player_id = ? AND quest_id = ?',
                                    (user_id, quest.id)
                                )
                                row = await cursor.fetchone()
                                if row:
                                    import json
                                    progress = json.loads(row[0])
                                    for i, obj in enumerate(quest.objectives):
                                        if progress[i] < obj.count:
                                            quest_text.append(f"📜 **{quest.title}**: {progress[i]}/{obj.count} {obj.description}")
                                            break
                    
                    if quest_text:
                        victory_embed.add_field(
                            name="📋 Quest Progress",
                            value="\n".join(quest_text),
                            inline=False
                        )
                
                # Get updated player stats
                async with await self.bot.db_connect() as db:
                    await db.execute('''
                        UPDATE players 
                        SET gold = gold + ?
                        WHERE id = ?
                    ''', (gold_dropped, user_id))
                    
                    await db.execute('''
                        UPDATE players 
                        SET health = ?, mana = ?, xp = ?, level = ?, 
                            max_health = ?, max_mana = ?,
                            in_combat = FALSE, current_enemy = NULL
                        WHERE id = ?
                    ''', (player.health, player.mana, player.xp, player.level, 
                          player.max_health, player.max_mana, user_id))
                    
                    cursor = await db.execute('''
                        SELECT level, health, max_health, mana, max_mana, xp, gold,
                               damage_bonus, magic_damage_bonus, defense, magic_defense,
                               crit_chance_bonus
                        FROM players WHERE id = ?
                    ''', (user_id,))
                    stats = await cursor.fetchone()
                    await db.commit()
                
                # Add stats footer
                if stats:
                    level, hp, max_hp, mana, max_mana, xp, gold, damage_bonus, magic_damage_bonus, defense, magic_defense, crit_chance_bonus = stats
                    xp_needed = level * 100
                    
                    # Format combat stats
                    combat_stats = f"⚔️ Damage: +{damage_bonus} | 🔮 Magic: +{magic_damage_bonus}\n"
                    combat_stats += f"🛡️ Defense: {defense} | 🌟 Magic Def: {magic_defense}\n"
                    combat_stats += f"💥 Crit Chance: +{crit_chance_bonus:.1f}%"
                    
                    victory_embed.add_field(
                        name="📊 Your Stats",
                        value=f"**Level {level}**\n"
                              f"HP: {hp}/{max_hp} | Mana: {mana}/{max_mana}\n"
                              f"XP: {xp}/{xp_needed} | Gold: {gold}\n"
                              f"{combat_stats}",
                        inline=False
                    )
                
                # Add action options footer
                victory_embed.add_field(
                    name="⚙️ Actions",
                    value="▶️ Next Quest\n🎒 Inventory\n📊 Stats\n🛡️ Equipment",
                    inline=False
                )
                
                victory_msg = await channel.send(embed=victory_embed)
                
                # Add reaction options
                await victory_msg.add_reaction("▶️")  # Next quest
                await victory_msg.add_reaction("🎒")  # Inventory
                await victory_msg.add_reaction("📊")  # Stats
                await victory_msg.add_reaction("🛡️")  # Equipment
                
                # Store victory message for reaction handling
                self.victory_messages[user_id] = {
                    'message_id': victory_msg.id,
                    'channel_id': channel.id
                }
                
                # Clean up combat
                del self.active_combats[user_id]
                return
            else:
                turn_history.append(f"🏃 {enemy.name} tried to flee but failed!")
                action = "attack"  # Fall back to attack
        
        if action == "heal":
            # Enemy heals itself
            heal_amount = random.randint(20, 40)
            old_health = enemy.health
            enemy.health = min(enemy.max_health, enemy.health + heal_amount)
            actual_heal = enemy.health - old_health
            
            turn_history.append(f"💚 {enemy.name} healed for {actual_heal} HP!")
        elif action == "attack":
            # Enemy attacks
            enemy_attack = random.choice(enemy.attacks)
            enemy_result = enemy_attack.execute(enemy, player)
            if enemy_result['success']:
                turn_history.append(f"🔴 {enemy.name} used {enemy_attack.name} - {enemy_result['damage']} damage to you!")
            else:
                turn_history.append(f"🔴 {enemy.name} tried {enemy_attack.name} - {enemy_result['message']}")
        
        # Build history display
        history_display = "\n".join(turn_history[-10:])
        
        enemy_embed = discord.Embed(
            title="⚔️ Combat - Enemy's Turn",
            description=f"**Combat History:**\n{history_display}",
            color=discord.Color.red()
        )
        enemy_embed.add_field(name="Your Stats", value=f"HP: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}", inline=True)
        enemy_embed.add_field(name="Enemy Stats", value=f"HP: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}", inline=True)
        await combat_msg.edit(embed=enemy_embed)
        
        # Update stats in database
        async with await self.bot.db_connect() as db:
            await db.execute('''
                UPDATE players 
                SET health = ?, mana = ?
                WHERE id = ?
            ''', (player.health, player.mana, player.id))
            await db.commit()
        
        # Check if player is defeated
        if not player.is_alive():
            # Record death in history before updating player
            async with await self.bot.db_connect() as db:
                await db.execute('''
                    INSERT INTO death_history (
                        player_id, enemy_name, enemy_level, 
                        player_level, player_health, player_max_health,
                        player_mana, player_max_mana
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, enemy.name, enemy.level, 
                      player.level, 0, player.max_health,
                      player.mana, player.max_mana))
                await db.commit()
            
            # Get current stats for display
            async with await self.bot.db_connect() as db:
                cursor = await db.execute('SELECT deaths FROM players WHERE id = ?', (user_id,))
                deaths_row = await cursor.fetchone()
                deaths = deaths_row[0] if deaths_row else 0
                
                cursor = await db.execute('SELECT COUNT(*) FROM player_kills WHERE player_id = ?', (user_id,))
                kills_row = await cursor.fetchone()
                kills = kills_row[0] if kills_row else 0
            
            defeat_embed = discord.Embed(
                title="💀 Defeat",
                description=f"You have died. Would you like to rest and play again?\n\n**Stats:**\n💀 Deaths: {deaths}\n⚔️ Kills: {kills}",
                color=discord.Color.red()
            )
            defeat_embed.add_field(
                name="Options",
                value=f"{self.RESTART_EMOJI} Rest and restart (penalty: 10% gold & XP)\n{self.LEAVE_EMOJI} Leave battle and view your status",
                inline=False
            )
            defeat_msg = await channel.send(embed=defeat_embed)
            
            # Add reaction options
            for emoji in self.defeat_emojis:
                await defeat_msg.add_reaction(emoji)
            
            # Store defeat message for reaction handling
            self.victory_messages[user_id] = {
                'message_id': defeat_msg.id,
                'type': 'defeat',
                'player': player
            }
            
            # Restore 50% health
            player.health = player.max_health // 2
            player.mana = player.max_mana
            
            # Update database - keep quest active for potential restart and increment deaths
            async with await self.bot.db_connect() as db:
                await db.execute('''
                    UPDATE players 
                    SET health = ?, mana = ?, in_combat = FALSE, current_enemy = NULL, deaths = deaths + 1
                    WHERE id = ?
                ''', (player.health, player.mana, player.id))
                await db.commit()
            
            # Clean up combat
            del self.active_combats[user_id]
            return
        
        # Wait a moment before showing next turn
        await asyncio.sleep(0.5)
        
        # Get healing item count
        healing_item_count = await self.get_healing_consumable_count(player.id)
        
        # Check if player has mana restore items (from stored combat data)
        has_mana_items = combat_data.get('has_mana_items', True)  # Default to True if not stored
        
        # Update message with combat status and options for next round
        actions_text = f"{self.MELEE_EMOJI} Melee Attack\n{self.MAGIC_EMOJI} Magic Attack\n{self.ITEM_EMOJI} Use Item"
        if healing_item_count > 0:
            actions_text += f" ({healing_item_count} healing items)"
        
        # Always show pray option
        actions_text += f"\n{self.PRAY_EMOJI} Pray (restore mana)"
        
        actions_text += f"\n{self.FLEE_EMOJI} Flee"
        
        # Build history display
        history_display = "\n".join(turn_history[-10:])  # Show last 10 turns
        
        options_embed = discord.Embed(
            title="⚔️ Combat - Your Turn",
            description=f"**Combat History:**\n{history_display}",
            color=discord.Color.blue()
        )
        options_embed.add_field(
            name="Your Stats",
            value=f"HP: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}",
            inline=True
        )
        options_embed.add_field(
            name="Enemy Stats",
            value=f"HP: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}",
            inline=True
        )
        options_embed.add_field(
            name="Actions",
            value=actions_text,
            inline=False
        )
        await combat_msg.edit(embed=options_embed)
        
        # Add fresh reactions
        for emoji in self.combat_emojis:
            await combat_msg.add_reaction(emoji)
        await combat_msg.add_reaction(self.PRAY_EMOJI)
        
        # Update stored combat data with message ID and turn history
        combat_data['message_id'] = combat_msg.id
        combat_data['turn_history'] = turn_history
    
    async def handle_enemy_turn(self, channel, user_id: int):
        """Handle just the enemy's turn (used after item usage)"""
        combat_data = self.active_combats.get(user_id)
        if not combat_data:
            return
            
        player = combat_data['player']
        enemy = combat_data['enemy']
        message_id = combat_data['message_id']
        turn_history = combat_data.get('turn_history', [])
        
        # Get the combat message to edit
        try:
            combat_msg = await channel.fetch_message(message_id)
        except:
            await channel.send("Combat message not found!")
            return
        
        # Enemy's turn - AI decision making
        await asyncio.sleep(0.5)
        
        # Determine enemy action based on health percentage
        health_percent = enemy.health / enemy.max_health
        action_roll = random.random()
        
        if health_percent < 0.3:
            # Low health: 60% heal, 30% attack, 10% flee
            if action_roll < 0.6:
                action = "heal"
            elif action_roll < 0.9:
                action = "attack"
            else:
                action = "flee"
        elif health_percent < 0.6:
            # Medium health: 70% attack, 20% heal, 10% flee
            if action_roll < 0.7:
                action = "attack"
            elif action_roll < 0.9:
                action = "heal"
            else:
                action = "flee"
        else:
            # High health: 85% attack, 10% heal, 5% flee
            if action_roll < 0.85:
                action = "attack"
            elif action_roll < 0.95:
                action = "heal"
            else:
                action = "flee"
        
        # Enemy regenerates mana to sustain the fight
        if enemy.mana < enemy.max_mana:
            mana_regen = int(enemy.max_mana * 0.3)  # 30% mana regeneration per turn
            enemy.mana = min(enemy.max_mana, enemy.mana + mana_regen)
        
        if action == "flee":
            # Enemy attempts to flee (handled same as in handle_combat_round)
            flee_chance = 0.15
            if random.random() < flee_chance:
                turn_history.append(f"🏃 {enemy.name} fled from battle!")
                history_display = "\n".join(turn_history[-10:])
                
                enemy_embed = discord.Embed(
                    title="Enemy Fled!",
                    description=f"**Combat History:**\n{history_display}",
                    color=discord.Color.orange()
                )
                await combat_msg.edit(embed=enemy_embed)
                enemy.health = 0
                # Victory sequence would be handled by checking enemy.health
                del self.active_combats[user_id]
                return
            else:
                turn_history.append(f"🏃 {enemy.name} tried to flee but failed!")
                action = "attack"
        
        if action == "heal":
            heal_amount = random.randint(20, 40)
            old_health = enemy.health
            enemy.health = min(enemy.max_health, enemy.health + heal_amount)
            actual_heal = enemy.health - old_health
            turn_history.append(f"💚 {enemy.name} healed for {actual_heal} HP!")
        elif action == "attack":
            enemy_attack = random.choice(enemy.attacks)
            enemy_result = enemy_attack.execute(enemy, player)
            if enemy_result['success']:
                turn_history.append(f"🔴 {enemy.name} used {enemy_attack.name} - {enemy_result['damage']} damage to you!")
            else:
                turn_history.append(f"🔴 {enemy.name} tried {enemy_attack.name} - {enemy_result['message']}")
        
        # Build history display
        history_display = "\n".join(turn_history[-10:])
        
        enemy_embed = discord.Embed(
            title="⚔️ Combat - Enemy's Turn",
            description=f"**Combat History:**\n{history_display}",
            color=discord.Color.red()
        )
        enemy_embed.add_field(name="Your Stats", value=f"HP: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}", inline=True)
        enemy_embed.add_field(name="Enemy Stats", value=f"HP: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}", inline=True)
        await combat_msg.edit(embed=enemy_embed)
        
        # Update stats in database
        async with await self.bot.db_connect() as db:
            await db.execute('''
                UPDATE players 
                SET health = ?, mana = ?
                WHERE id = ?
            ''', (player.health, player.mana, player.id))
            await db.commit()
        
        # Check if player is defeated
        if not player.is_alive():
            # Record death and handle defeat (same as handle_combat_round)
            async with await self.bot.db_connect() as db:
                await db.execute('''
                    INSERT INTO death_history (
                        player_id, enemy_name, enemy_level, 
                        player_level, player_health, player_max_health,
                        player_mana, player_max_mana
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (user_id, enemy.name, enemy.level, 
                      player.level, 0, player.max_health,
                      player.mana, player.max_mana))
                await db.commit()
            
            # Get current stats for display
            async with await self.bot.db_connect() as db:
                cursor = await db.execute('SELECT deaths FROM players WHERE id = ?', (user_id,))
                deaths_row = await cursor.fetchone()
                deaths = deaths_row[0] if deaths_row else 0
                
                cursor = await db.execute('SELECT COUNT(*) FROM player_kills WHERE player_id = ?', (user_id,))
                kills_row = await cursor.fetchone()
                kills = kills_row[0] if kills_row else 0
            
            defeat_embed = discord.Embed(
                title="💀 Defeat",
                description=f"You have died. Would you like to rest and play again?\n\n**Stats:**\n💀 Deaths: {deaths}\n⚔️ Kills: {kills}",
                color=discord.Color.red()
            )
            defeat_embed.add_field(
                name="Options",
                value=f"{self.RESTART_EMOJI} Rest and restart (penalty: 10% gold & XP)\n{self.LEAVE_EMOJI} Leave battle and view your status",
                inline=False
            )
            defeat_msg = await channel.send(embed=defeat_embed)
            
            for emoji in self.defeat_emojis:
                await defeat_msg.add_reaction(emoji)
            
            self.victory_messages[user_id] = {
                'message_id': defeat_msg.id,
                'type': 'defeat',
                'player': player
            }
            
            player.health = player.max_health // 2
            player.mana = player.max_mana
            
            async with await self.bot.db_connect() as db:
                await db.execute('''
                    UPDATE players 
                    SET health = ?, mana = ?, in_combat = FALSE, current_enemy = NULL, deaths = deaths + 1
                    WHERE id = ?
                ''', (player.health, player.mana, player.id))
                await db.commit()
            
            del self.active_combats[user_id]
            return
        
        # Wait before showing next turn
        await asyncio.sleep(0.5)
        
        # Get healing item count
        healing_item_count = await self.get_healing_consumable_count(player.id)
        
        # Check if player has mana restore items (from stored combat data)
        has_mana_items = combat_data.get('has_mana_items', True)  # Default to True if not stored
        
        # Update message with combat status and options for next round
        actions_text = f"{self.MELEE_EMOJI} Melee Attack\n{self.MAGIC_EMOJI} Magic Attack\n{self.ITEM_EMOJI} Use Item"
        if healing_item_count > 0:
            actions_text += f" ({healing_item_count} healing items)"
        
        # Always show pray option
        actions_text += f"\n{self.PRAY_EMOJI} Pray (restore mana)"
        
        actions_text += f"\n{self.FLEE_EMOJI} Flee"
        
        # Build history display
        history_display = "\n".join(turn_history[-10:])
        
        options_embed = discord.Embed(
            title="⚔️ Combat - Your Turn",
            description=f"**Combat History:**\n{history_display}",
            color=discord.Color.blue()
        )
        options_embed.add_field(
            name="Your Stats",
            value=f"HP: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}",
            inline=True
        )
        options_embed.add_field(
            name="Enemy Stats",
            value=f"HP: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}",
            inline=True
        )
        options_embed.add_field(
            name="Actions",
            value=actions_text,
            inline=False
        )
        await combat_msg.edit(embed=options_embed)
        
        # Add fresh reactions
        for emoji in self.combat_emojis:
            await combat_msg.add_reaction(emoji)
        await combat_msg.add_reaction(self.PRAY_EMOJI)
        
        # Update stored combat data
        combat_data['message_id'] = combat_msg.id
        combat_data['turn_history'] = turn_history
    
    async def get_healing_consumable_count(self, user_id: int) -> int:
        """Get the count of healing consumables in player's inventory"""
        async with await self.bot.db_connect() as db:
            cursor = await db.execute('''
                SELECT item_id, count FROM inventory 
                WHERE player_id = ? AND count > 0
            ''', (user_id,))
            items = await cursor.fetchall()
        
        total_healing_items = 0
        for item_id, count in items:
            item = self.inventory_manager.items.get(item_id)
            if item and item.type == ItemType.CONSUMABLE:
                # Check if item has healing or mana restore effects
                for effect in item.effects:
                    if effect.type in ["health_bonus", "mana_bonus", "heal", "mana_restore"]:
                        total_healing_items += count
                        break
        
        return total_healing_items
        
    async def handle_flee(self, channel, user, combat_data):
        """Handle flee attempt"""
        if random.random() < 0.5:
            # Successful flee
            player = combat_data['player']
            enemy = combat_data['enemy']
            
            # Update player state in database
            async with await self.bot.db_connect() as db:
                await db.execute('''
                    UPDATE players 
                    SET health = ?, mana = ?, in_combat = FALSE, current_enemy = NULL
                    WHERE id = ?
                ''', (player.health, player.mana, user.id))
                await db.commit()
            
            # Clear combat data
            del self.active_combats[user.id]
            
            # Clear reactions from combat message
            message = await channel.fetch_message(combat_data['message_id'])
            await message.clear_reactions()
            
            # Send flee success message with action buttons
            flee_embed = discord.Embed(
                title="🏃 Fled from Combat!",
                description=f"{user.mention} successfully escaped from **{enemy.name}**!",
                color=discord.Color.orange()
            )
            flee_embed.add_field(
                name="Current Status",
                value=f"HP: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}",
                inline=False
            )
            flee_embed.add_field(
                name="What would you like to do?",
                value=f"🛏️ Rest (restore HP and Mana)\n🔄 Retry Quest (start combat again)\n🎒 View Inventory\n📊 View Stats\n🛡️ View Equipment",
                inline=False
            )
            
            flee_msg = await channel.send(embed=flee_embed)
            
            # Add reaction buttons
            await flee_msg.add_reaction("🛏️")  # Rest
            await flee_msg.add_reaction("🔄")  # Retry quest
            await flee_msg.add_reaction("🎒")  # Inventory
            await flee_msg.add_reaction("📊")  # Stats
            await flee_msg.add_reaction("🛡️")  # Equipment
            
            # Store flee message for reaction handling
            self.victory_messages[user.id] = {
                'message_id': flee_msg.id,
                'channel_id': channel.id,
                'type': 'flee'
            }
        else:
            # Failed to flee - update combat log
            player = combat_data['player']
            enemy = combat_data['enemy']
            turn_history = combat_data.get('turn_history', [])
            message_id = combat_data['message_id']
            
            # Add failed flee to turn history
            turn_history.append(f"🏃 {player.name} tried to flee but the enemy blocked the escape!")
            self.active_combats[user.id]['turn_history'] = turn_history
            
            # Update the combat message
            try:
                combat_msg = await channel.fetch_message(message_id)
                
                # Build history display
                history_display = "\n".join(turn_history[-10:])
                
                # Check if player has mana restore items (from stored combat data)
                has_mana_items = combat_data.get('has_mana_items', True)
                
                # Get healing item count
                healing_item_count = await self.get_healing_consumable_count(player.id)
                
                # Build actions text
                actions_text = f"{self.MELEE_EMOJI} Melee Attack\n{self.MAGIC_EMOJI} Magic Attack\n{self.ITEM_EMOJI} Use Item"
                if healing_item_count > 0:
                    actions_text += f" ({healing_item_count} healing items)"
                
                # Always show pray option
                if not has_mana_items:
                    actions_text += f"\n{self.PRAY_EMOJI} Pray (restore mana)"
                
                actions_text += f"\n{self.FLEE_EMOJI} Flee"
                
                flee_fail_embed = discord.Embed(
                    title="🏃 Flee Failed!",
                    description=f"**Combat History:**\n{history_display}",
                    color=discord.Color.red()
                )
                flee_fail_embed.add_field(name="Your Stats", value=f"HP: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}", inline=True)
                flee_fail_embed.add_field(name="Enemy Stats", value=f"HP: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}", inline=True)
                flee_fail_embed.add_field(name="Actions", value=actions_text, inline=False)
                
                await combat_msg.edit(embed=flee_fail_embed)
                await combat_msg.clear_reactions()
            except Exception as e:
                logger.error(f"Error updating combat message after failed flee: {e}")
            
            # Enemy gets a turn for punishing the failed flee attempt
            await asyncio.sleep(1)
            await self.handle_enemy_turn(channel, user.id)
    
    async def has_mana_restore_items(self, user_id):
        """Check if player has any mana restore consumables"""
        async with await self.bot.db_connect() as db:
            cursor = await db.execute('''
                SELECT item_id, count FROM inventory 
                WHERE player_id = ? AND count > 0
            ''', (user_id,))
            items = await cursor.fetchall()
        
        for item_id, count in items:
            item = self.inventory_manager.items.get(item_id)
            if item and item.type == ItemType.CONSUMABLE:
                # Check if any effect is mana_restore
                for effect in item.effects:
                    if effect.type == "mana_restore" or effect.type == "restore_mana":
                        return True
        return False
    
    async def handle_item_usage(self, channel, user, combat_data):
        """Handle consumable item usage during combat"""
        # Get player's consumable items
        async with await self.bot.db_connect() as db:
            cursor = await db.execute('''
                SELECT item_id, count FROM inventory 
                WHERE player_id = ? AND count > 0
            ''', (user.id,))
            items = await cursor.fetchall()
        
        if not items:
            await channel.send(f"{user.mention} You have no items in your inventory!")
            return
        
        # Filter consumables
        consumables = []
        for item_id, count in items:
            item = self.inventory_manager.items.get(item_id)
            if item and item.type == ItemType.CONSUMABLE:
                consumables.append((item, count))
        
        if not consumables:
            await channel.send(f"{user.mention} You have no consumable items!")
            return
        
        # Create item selection embed
        embed = discord.Embed(
            title="🧪 Use Item",
            description="React with the number to use an item:",
            color=discord.Color.green()
        )
        
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        for i, (item, count) in enumerate(consumables[:9]):  # Limit to 9 items
            embed.add_field(
                name=f"{number_emojis[i]} {item.name} (x{count})",
                value=item.description,
                inline=False
            )
        
        item_msg = await channel.send(embed=embed)
        
        # Add number reactions
        for i in range(min(len(consumables), 9)):
            await item_msg.add_reaction(number_emojis[i])
        await item_msg.add_reaction("❌")  # Cancel option
        
        def check(reaction, reactor):
            return (reactor.id == user.id and 
                    reaction.message.id == item_msg.id and
                    str(reaction.emoji) in number_emojis[:len(consumables)] + ["❌"])
        
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == "❌":
                await item_msg.delete()
                return
            
            # Find which item was selected
            selected_index = number_emojis.index(str(reaction.emoji))
            selected_item, _ = consumables[selected_index]
            
            # Apply item effects
            player = combat_data['player']
            enemy = combat_data['enemy']
            
            effects_applied = []
            for effect in selected_item.effects:
                if effect.type in ["health_bonus", "heal"]:
                    heal_amount = min(effect.value, player.max_health - player.health)
                    player.health += heal_amount
                    effects_applied.append(f"Restored {heal_amount} HP")
                elif effect.type in ["mana_bonus", "mana_restore"]:
                    mana_amount = min(effect.value, player.max_mana - player.mana)
                    player.mana += mana_amount
                    effects_applied.append(f"Restored {mana_amount} Mana")
                elif effect.type == "damage":
                    enemy.health -= effect.value
                    effects_applied.append(f"Dealt {effect.value} damage to {enemy.name}")
            
            # Remove item from inventory
            async with await self.bot.db_connect() as db:
                await db.execute('''
                    UPDATE inventory 
                    SET count = count - 1 
                    WHERE player_id = ? AND item_id = ?
                ''', (user.id, selected_item.id))
                
                # Remove if count reaches 0
                await db.execute('''
                    DELETE FROM inventory 
                    WHERE player_id = ? AND item_id = ? AND count <= 0
                ''', (user.id, selected_item.id))
                
                await db.commit()
            
            # Update combat data
            self.active_combats[user.id]['player'] = player
            self.active_combats[user.id]['enemy'] = enemy
            
            # Add item usage to turn history
            turn_history = combat_data.get('turn_history', [])
            turn_history.append(f"🧪 You used {selected_item.name} - " + ", ".join(effects_applied))
            self.active_combats[user.id]['turn_history'] = turn_history
            
            await item_msg.delete()
            
            # Check if enemy is defeated
            if enemy.health <= 0:
                # Enemy defeated by item! Trigger the normal victory sequence
                # We need to call handle_combat_round with a fake attack to trigger victory
                await channel.send(f"💀 {enemy.name} was defeated by the {selected_item.name}!")
                # The victory logic is in handle_combat_round, but we need enemy.health to be 0
                # Just delete combat and return - the next check will handle it
                message_id = combat_data['message_id']
                try:
                    combat_msg = await channel.fetch_message(message_id)
                    # Continue with the victory check by triggering handle_combat_round with melee
                    # This will see enemy is dead and trigger victory
                    await self.handle_combat_round(channel, user.id, "melee")
                except:
                    pass
                return
            
            # Update the combat message to show item was used
            message_id = combat_data['message_id']
            try:
                combat_msg = await channel.fetch_message(message_id)
                
                # Build history display
                history_display = "\n".join(turn_history[-10:])
                
                item_embed = discord.Embed(
                    title="🧪 Item Used",
                    description=f"**Combat History:**\n{history_display}",
                    color=discord.Color.green()
                )
                item_embed.add_field(name="Your Stats", value=f"HP: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}", inline=True)
                item_embed.add_field(name="Enemy Stats", value=f"HP: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}", inline=True)
                await combat_msg.edit(embed=item_embed)
                await combat_msg.clear_reactions()
            except:
                pass
            
            # Enemy's turn now - call the enemy turn logic
            await asyncio.sleep(1)
            await self.handle_enemy_turn(channel, user.id)
                
        except asyncio.TimeoutError:
            await item_msg.delete()
            await channel.send(f"{user.mention} Item selection timed out.")
    
    async def handle_pray(self, channel, user_id):
        """Handle pray action - restore random amount of mana"""
        combat_data = self.active_combats.get(user_id)
        if not combat_data:
            return
        
        player = combat_data['player']
        enemy = combat_data['enemy']
        message_id = combat_data['message_id']
        turn_history = combat_data.get('turn_history', [])
        
        # Restore random amount of mana (20-40% of max mana)
        restore_percent = random.uniform(0.20, 0.40)
        mana_restored = int(player.max_mana * restore_percent)
        mana_restored = min(mana_restored, player.max_mana - player.mana)
        
        player.mana += mana_restored
        
        # Add to turn history
        turn_history.append(f"🙏 {player.name} prayed to the gods and restored {mana_restored} mana!")
        self.active_combats[user_id]['turn_history'] = turn_history
        self.active_combats[user_id]['player'] = player
        
        # Update the combat message to show prayer was used
        try:
            combat_msg = await channel.fetch_message(message_id)
            
            # Build history display
            history_display = "\n".join(turn_history[-10:])
            
            # Check if player has mana restore items (from stored combat data)
            has_mana_items = combat_data.get('has_mana_items', True)
            
            # Get healing item count
            healing_item_count = await self.get_healing_consumable_count(player.id)
            
            # Build actions text
            actions_text = f"{self.MELEE_EMOJI} Melee Attack\n{self.MAGIC_EMOJI} Magic Attack\n{self.ITEM_EMOJI} Use Item"
            if healing_item_count > 0:
                actions_text += f" ({healing_item_count} healing items)"
            
            # Always show pray option
            actions_text += f"\n{self.PRAY_EMOJI} Pray (restore mana)"
            
            actions_text += f"\n{self.FLEE_EMOJI} Flee"
            
            pray_embed = discord.Embed(
                title="🙏 Prayer",
                description=f"**Combat History:**\n{history_display}",
                color=discord.Color.gold()
            )
            pray_embed.add_field(name="Your Stats", value=f"HP: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}", inline=True)
            pray_embed.add_field(name="Enemy Stats", value=f"HP: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}", inline=True)
            pray_embed.add_field(name="Actions", value=actions_text, inline=False)
            
            await combat_msg.edit(embed=pray_embed)
            await combat_msg.clear_reactions()
        except Exception as e:
            logger.error(f"Error updating combat message after prayer: {e}")
        
        # Enemy gets a turn
        await asyncio.sleep(1)
        await self.handle_enemy_turn(channel, user_id)
    
    async def handle_victory_action(self, reaction, user):
        """Handle post-combat victory and defeat actions"""
        emoji = str(reaction.emoji)
        
        try:
            # Remove the reaction
            await reaction.remove(user)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
            logger.warning(f"Could not remove reaction: {str(e)}")
        
        # Check if this is a defeat reaction
        victory_data = self.victory_messages.get(user.id)
        if victory_data and victory_data.get('type') == 'defeat':
            if emoji == self.RESTART_EMOJI:  # Heal and restart quest
                await self.handle_defeat_restart(reaction.message.channel, user)
            elif emoji == self.LEAVE_EMOJI:  # Leave battle and view status
                await self.handle_defeat_leave(reaction.message.channel, user)
            return
        
        # Check if this is a flee reaction
        if victory_data and victory_data.get('type') == 'flee':
            if emoji == "🛏️":  # Rest to restore HP/Mana
                await self.handle_rest(reaction.message.channel, user)
            elif emoji == "🔄":  # Retry quest (restart combat)
                await self.handle_flee_retry(reaction.message.channel, user)
            elif emoji == "🎒":  # Show Inventory
                await self.handle_show_inventory(reaction.message.channel, user)
            elif emoji == "📊":  # Show Stats
                await self.handle_show_stats(reaction.message.channel, user)
            elif emoji == "🛡️":  # Show Equipment
                await self.handle_show_equipment(reaction.message.channel, user)
            return
        
        # Check if this is a rest reaction
        if victory_data and victory_data.get('type') == 'rest':
            if emoji == "▶️":  # Next Quest
                await self.handle_next_quest(reaction.message.channel, user)
            elif emoji == "🔄":  # Retry quest (restart combat)
                await self.handle_flee_retry(reaction.message.channel, user)
            elif emoji == "🎒":  # Show Inventory
                await self.handle_show_inventory(reaction.message.channel, user)
            elif emoji == "📊":  # Show Stats
                await self.handle_show_stats(reaction.message.channel, user)
            elif emoji == "🛡️":  # Show Equipment
                await self.handle_show_equipment(reaction.message.channel, user)
            return
        
        # Victory reactions
        if emoji == "🛏️":  # Rest to restore HP/Mana
            await self.handle_rest(reaction.message.channel, user)
        elif emoji == "▶️":  # Next Quest
            await self.handle_next_quest(reaction.message.channel, user)
        elif emoji == "🎒":  # Show Inventory
            await self.handle_show_inventory(reaction.message.channel, user)
        elif emoji == "📊":  # Show Stats
            await self.handle_show_stats(reaction.message.channel, user)
        elif emoji == "🛡️":  # Show Equipment
            await self.handle_show_equipment(reaction.message.channel, user)
    
    async def handle_next_quest(self, channel, user):
        """Activate the next available quest"""
        async with await self.bot.db_connect() as db:
            # Get the player's current level
            cursor = await db.execute('''
                SELECT level FROM players WHERE id = ?
            ''', (user.id,))
            player_data = await cursor.fetchone()
            
            if not player_data:
                await channel.send(f"{user.mention} No player data found!")
                return
            
            player_level = player_data[0]
            
            # Get all quests for the player
            cursor = await db.execute('''
                SELECT quest_id, completed FROM active_quests 
                WHERE player_id = ?
                ORDER BY completed ASC
            ''', (user.id,))
            active_quests = await cursor.fetchall()
            
            logger.info(f"Next Quest - Active quests for user {user.id}: {active_quests}")
            
            # Build lists - completed should be 1 (TRUE) or 0 (FALSE)
            active_incomplete = []
            completed_quest_ids = []
            
            for quest_id, completed in active_quests:
                logger.info(f"Quest {quest_id}: completed={completed} (type: {type(completed)})")
                # SQLite returns 0 or 1 for boolean
                if completed == 1 or completed == True:
                    completed_quest_ids.append(quest_id)
                else:
                    active_incomplete.append(quest_id)
            
            logger.info(f"Incomplete quests: {active_incomplete}")
            logger.info(f"Completed quests: {completed_quest_ids}")
            
            # Check if there's an incomplete quest that is the next quest in the chain
            next_quest_in_chain = None
            for completed_id in completed_quest_ids:
                completed_quest = self.quest_manager.quests.get(completed_id)
                if completed_quest and hasattr(completed_quest, 'next_quest') and completed_quest.next_quest:
                    if completed_quest.next_quest in active_incomplete:
                        # The next quest is already active but incomplete - this is fine, continue it
                        next_quest_in_chain = completed_quest.next_quest
                        break
            
            # If there's an active incomplete quest, use it as the quest to continue
            current_quest_id = next_quest_in_chain if next_quest_in_chain else (active_incomplete[0] if active_incomplete else None)
            
            # If we have an active quest, start combat for it if it's a combat quest
            if current_quest_id:
                quest = self.quest_manager.quests.get(current_quest_id)
                
                # If it's a combat quest, start combat automatically
                if quest and quest.type == QuestType.COMBAT:
                    await channel.send(f"⚔️ {user.mention} Continuing quest: **{quest.title}**")
                    # Start combat for the quest
                    await self.start_quest_combat(channel, user.id)
                elif quest and quest.objectives and quest.objectives[0].type == ObjectiveType.COMBAT:
                    # Check if first objective is combat (for exploration/collection quests with combat objectives)
                    await channel.send(f"⚔️ {user.mention} Continuing quest: **{quest.title}**")
                    await self.start_quest_combat(channel, user.id)
                elif quest:
                    await channel.send(f"📜 {user.mention} Continue your quest: **{quest.title}**\n{quest.description}")
                return
            
            # Find the next quest based on completed quests
            next_quest = None
            
            # Check if any completed quest has a next_quest defined
            for completed_id in completed_quest_ids:
                completed_quest = self.quest_manager.quests.get(completed_id)
                if completed_quest and hasattr(completed_quest, 'next_quest') and completed_quest.next_quest:
                    # Check if this next quest hasn't been started yet
                    all_quest_ids = [q[0] for q in active_quests]
                    logger.info(f"Checking next_quest '{completed_quest.next_quest}' from completed quest '{completed_id}'")
                    logger.info(f"All quest IDs: {all_quest_ids}")
                    if completed_quest.next_quest not in all_quest_ids:
                        potential_quest = self.quest_manager.quests.get(completed_quest.next_quest)
                        if potential_quest and potential_quest.requirements.get('level', 1) <= player_level:
                            logger.info(f"Found next quest: {potential_quest.title}")
                            next_quest = potential_quest
                            break
            
            # If no next quest found from completed quests, find first available quest
            if not next_quest:
                all_active_ids = [q[0] for q in active_quests]
                for quest_id, quest in self.quest_manager.quests.items():
                    if quest_id not in all_active_ids:
                        if quest.requirements.get('level', 1) <= player_level:
                            # Check if it requires a previous quest
                            if 'previous_quest' in quest.requirements:
                                if quest.requirements['previous_quest'] in completed_quest_ids:
                                    next_quest = quest
                                    break
                            else:
                                next_quest = quest
                                break
            
            if next_quest:
                logger.info(f"Starting next quest: {next_quest.id}")
                # Start the quest
                success = await self.quest_manager.start_quest(user.id, next_quest.id)
                if success:
                    await channel.send(f"✅ {user.mention} Started quest: **{next_quest.title}**\n{next_quest.description}")
                    
                    # Auto-start combat if it's a combat quest
                    if next_quest.type == QuestType.COMBAT:
                        logger.info(f"Auto-starting combat for quest {next_quest.id}")
                        await self.start_quest_combat(channel, user.id)
                    elif next_quest.objectives and next_quest.objectives[0].type == ObjectiveType.COMBAT:
                        # Check if first objective is combat (for exploration/collection quests with combat objectives)
                        logger.info(f"Auto-starting combat for {next_quest.type.value} quest {next_quest.id}")
                        await self.start_quest_combat(channel, user.id)
                else:
                    await channel.send(f"{user.mention} Failed to start quest.")
            else:
                logger.info("No next quest found")
                await channel.send(f"{user.mention} No new quests available at the moment!")
    
    async def handle_show_inventory(self, channel, user):
        """Display the player's inventory"""
        async with await self.bot.db_connect() as db:
            cursor = await db.execute('''
                SELECT item_id, count FROM inventory 
                WHERE player_id = ? AND count > 0
                ORDER BY item_id
            ''', (user.id,))
            items = await cursor.fetchall()
            
            if not items:
                await channel.send(f"{user.mention} Your inventory is empty!")
                return
            
            embed = discord.Embed(
                title=f"🎒 {user.display_name}'s Inventory",
                color=discord.Color.blue()
            )
            
            # Group items by type
            weapons = []
            armor = []
            consumables = []
            other = []
            
            for item_id, count in items:
                item = self.inventory_manager.items.get(item_id)
                if item:
                    item_text = f"{item.name} x{count}"
                    if item.type == ItemType.WEAPON:
                        weapons.append(item_text)
                    elif item.type in [ItemType.HELMET, ItemType.ARMOR, ItemType.PANTS, ItemType.BOOTS]:
                        armor.append(item_text)
                    elif item.type == ItemType.CONSUMABLE:
                        consumables.append(item_text)
                    else:
                        other.append(item_text)
            
            if weapons:
                embed.add_field(name="⚔️ Weapons", value="\n".join(weapons), inline=False)
            if armor:
                embed.add_field(name="🛡️ Armor", value="\n".join(armor), inline=False)
            if consumables:
                embed.add_field(name="🧪 Consumables", value="\n".join(consumables), inline=False)
            if other:
                embed.add_field(name="📦 Other", value="\n".join(other), inline=False)
            
            await channel.send(embed=embed)
    
    async def handle_show_stats(self, channel, user):
        """Display the player's stats"""
        async with await self.bot.db_connect() as db:
            cursor = await db.execute('''
                SELECT name, level, health, max_health, mana, max_mana, xp, gold,
                       damage_bonus, health_bonus, mana_bonus, crit_chance_bonus
                FROM players WHERE id = ?
            ''', (user.id,))
            player_data = await cursor.fetchone()
            
            if not player_data:
                await channel.send(f"{user.mention} No player data found!")
                return
            
            name, level, hp, max_hp, mana, max_mana, xp, gold, dmg, hp_bonus, mana_bonus, crit = player_data
            xp_needed = level * 100
            
            embed = discord.Embed(
                title=f"📊 {name}'s Stats",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Core Stats",
                value=f"**Level:** {level}\n"
                      f"**HP:** {hp}/{max_hp}\n"
                      f"**Mana:** {mana}/{max_mana}\n"
                      f"**XP:** {xp}/{xp_needed}\n"
                      f"**Gold:** {gold}",
                inline=True
            )
            
            embed.add_field(
                name="Combat Bonuses",
                value=f"**Damage:** +{dmg}\n"
                      f"**Health:** +{hp_bonus}\n"
                      f"**Mana:** +{mana_bonus}\n"
                      f"**Crit Chance:** +{crit}%",
                inline=True
            )
            
            await channel.send(embed=embed)
    
    async def handle_show_equipment(self, channel, user):
        """Display the player's equipped items in Diablo 2 style layout"""
        from ..models.inventory import ItemRarity
        
        equipment = await self.inventory_manager.get_equipment(user.id)
        if not equipment:
            await channel.send(f"{user.mention} No equipment found!")
            return

        def format_item(item):
            """Format an item with its effects"""
            if not item:
                return "*(Empty)*"
            
            rarity_prefix = "⚪" if item.rarity == ItemRarity.COMMON else \
                          "🟢" if item.rarity == ItemRarity.UNCOMMON else \
                          "🔵" if item.rarity == ItemRarity.RARE else \
                          "🟣" if item.rarity == ItemRarity.EPIC else "🟡"
            
            result = f"{rarity_prefix} **{item.name}** *(Lvl {item.level_requirement})*"
            
            # Add item effects on same line
            if item.effects:
                effects = []
                for effect_obj in item.effects:
                    effect_type = effect_obj.type
                    effect_value = effect_obj.value
                    
                    if effect_value != 0:
                        if effect_type == 'damage':
                            effects.append(f"+{effect_value} Dmg")
                        elif effect_type == 'magic_damage':
                            effects.append(f"+{effect_value} Magic")
                        elif effect_type == 'defense':
                            effects.append(f"+{effect_value} Def")
                        elif effect_type == 'magic_defense':
                            effects.append(f"+{effect_value} M.Def")
                        elif effect_type == 'crit_chance':
                            effects.append(f"+{effect_value}% Crit")
                        elif effect_type == 'health_bonus':
                            effects.append(f"+{effect_value} HP")
                        elif effect_type == 'mana_bonus':
                            effects.append(f"+{effect_value} Mana")
                        elif effect_type == 'flee_chance':
                            effects.append(f"+{effect_value}% Flee")
                if effects:
                    result += "\n" + " | ".join(effects)
            
            return result

        embed = discord.Embed(
            title=f"⚔️ {user.name}'s Equipment",
            color=discord.Color.gold()
        )

        # Simple left-aligned list
        embed.add_field(name="🪖 Helmet", value=format_item(equipment.helmet), inline=False)
        embed.add_field(name="📿 Amulet", value=format_item(equipment.amulet), inline=False)
        embed.add_field(name="⚔️ Weapon", value=format_item(equipment.weapon), inline=False)
        embed.add_field(name="🥋 Armor", value=format_item(equipment.armor), inline=False)
        embed.add_field(name="💍 Ring 1", value=format_item(equipment.ring1), inline=False)
        embed.add_field(name="💍 Ring 2", value=format_item(equipment.ring2), inline=False)
        embed.add_field(name="👖 Pants", value=format_item(equipment.pants), inline=False)
        embed.add_field(name="👢 Boots", value=format_item(equipment.boots), inline=False)

        # Add total stats summary
        stats = equipment.get_total_stats()
        stats_text = []
        if stats.get('damage', 0) > 0:
            stats_text.append(f"⚔️ +{stats['damage']} Damage")
        if stats.get('magic_damage', 0) > 0:
            stats_text.append(f"🔮 +{stats['magic_damage']} Magic Damage")
        if stats.get('defense', 0) > 0:
            stats_text.append(f"🛡️ +{stats['defense']} Defense")
        if stats.get('magic_defense', 0) > 0:
            stats_text.append(f"✨ +{stats['magic_defense']} Magic Defense")
        if stats.get('crit_chance', 0) > 0:
            stats_text.append(f"💥 +{stats['crit_chance']}% Crit Chance")
        if stats.get('health_bonus', 0) > 0:
            stats_text.append(f"❤️ +{stats['health_bonus']} Max HP")
        if stats.get('mana_bonus', 0) > 0:
            stats_text.append(f"💙 +{stats['mana_bonus']} Max Mana")

        if stats_text:
            embed.add_field(
                name="📊 Total Bonuses",
                value=" | ".join(stats_text),
                inline=False
            )

        await channel.send(embed=embed)
    
    async def handle_rest(self, channel, user):
        """Allow the player to rest and restore HP and Mana"""
        async with await self.bot.db_connect() as db:
            # Get player data
            cursor = await db.execute('''
                SELECT name, health, max_health, mana, max_mana FROM players WHERE id = ?
            ''', (user.id,))
            player_data = await cursor.fetchone()
            
            if not player_data:
                await channel.send(f"{user.mention} No player data found!")
                return
            
            name, current_hp, max_hp, current_mana, max_mana = player_data
            
            # Calculate HP and Mana restored
            hp_restored = max_hp - current_hp
            mana_restored = max_mana - current_mana
            
            # Update player to full HP and Mana
            await db.execute('''
                UPDATE players
                SET health = max_health, mana = max_mana
                WHERE id = ?
            ''', (user.id,))
            await db.commit()
            
            # Create rest message
            embed = discord.Embed(
                title="🛏️ Rest",
                description=f"{name} takes a moment to rest and recover...",
                color=discord.Color.blue()
            )
            
            if hp_restored > 0 or mana_restored > 0:
                recovery_text = []
                if hp_restored > 0:
                    recovery_text.append(f"❤️ HP: {current_hp} → {max_hp} (+{hp_restored})")
                if mana_restored > 0:
                    recovery_text.append(f"💙 Mana: {current_mana} → {max_mana} (+{mana_restored})")
                
                embed.add_field(
                    name="Recovery",
                    value="\n".join(recovery_text),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Status",
                    value="You're already at full health and mana!",
                    inline=False
                )
            
            embed.add_field(
                name="Ready for Battle",
                value="You feel refreshed and ready to continue your adventure!",
                inline=False
            )
            
            embed.add_field(
                name="What would you like to do?",
                value=f"▶️ Next Quest\n🔄 Retry Quest (start combat again)\n🎒 View Inventory\n📊 View Stats\n🛡️ View Equipment",
                inline=False
            )
            
            rest_msg = await channel.send(embed=embed)
            
            # Add reaction buttons
            await rest_msg.add_reaction("▶️")  # Next quest
            await rest_msg.add_reaction("🔄")  # Retry quest
            await rest_msg.add_reaction("🎒")  # Inventory
            await rest_msg.add_reaction("📊")  # Stats
            await rest_msg.add_reaction("🛡️")  # Equipment
            
            # Store rest message for reaction handling (reuse victory_messages)
            # Clean up old victory message first
            if user.id in self.victory_messages:
                del self.victory_messages[user.id]
            
            # Store new rest message
            self.victory_messages[user.id] = {
                'message_id': rest_msg.id,
                'channel_id': channel.id,
                'type': 'rest'
            }
    
    async def handle_flee_retry(self, channel, user):
        """Handle retrying combat after fleeing"""
        # Clean up flee message tracking
        if user.id in self.victory_messages:
            del self.victory_messages[user.id]
        
        # Simply start quest combat again
        await channel.send(f"{user.mention} You steel your courage and prepare to face your foe once more!")
        await self.start_quest_combat(channel, user.id)
    
    async def handle_defeat_restart(self, channel, user):
        """Handle defeat restart - heal fully, apply penalties, and restart quest"""
        async with await self.bot.db_connect() as db:
            # Get player data
            cursor = await db.execute('''
                SELECT max_health, max_mana, gold, xp, level FROM players WHERE id = ?
            ''', (user.id,))
            player_data = await cursor.fetchone()
            
            if not player_data:
                await channel.send(f"{user.mention} No player data found!")
                return
            
            max_hp, max_mana, gold, xp, level = player_data
            
            # Apply 10% penalty to gold and XP
            gold_penalty = int(gold * 0.1)
            xp_penalty = int(xp * 0.1)
            new_gold = max(0, gold - gold_penalty)
            new_xp = max(0, xp - xp_penalty)
            
            # Update to full health and mana, apply penalties
            await db.execute('''
                UPDATE players 
                SET health = ?, mana = ?, gold = ?, xp = ?
                WHERE id = ?
            ''', (max_hp, max_mana, new_gold, new_xp, user.id))
            await db.commit()
            
            # Get current quest
            cursor = await db.execute('''
                SELECT quest_id FROM active_quests 
                WHERE player_id = ? AND completed = FALSE
                LIMIT 1
            ''', (user.id,))
            quest_data = await cursor.fetchone()
            
            penalty_msg = ""
            if gold_penalty > 0 or xp_penalty > 0:
                penalty_msg = f"\n**Penalty:** -{gold_penalty} gold, -{xp_penalty} XP"
            
            if quest_data:
                quest_id = quest_data[0]
                quest = self.quest_manager.quests.get(quest_id)
                
                await channel.send(
                    f"✨ {user.mention} You have rested and recovered!\n"
                    f"**HP:** {max_hp}/{max_hp} | **Mana:** {max_mana}/{max_mana}{penalty_msg}\n"
                    f"Restarting quest: **{quest.title}**"
                )
                
                # Start quest combat
                await self.start_quest_combat(channel, user.id)
            else:
                await channel.send(
                    f"✨ {user.mention} You have rested and recovered!\n"
                    f"**HP:** {max_hp}/{max_hp} | **Mana:** {max_mana}/{max_mana}{penalty_msg}\n"
                    f"No active quest to restart. Use `!w quests` to view available quests."
                )
    
    async def handle_defeat_leave(self, channel, user):
        """Handle defeat leave - show stats, inventory, and current quest"""
        # Show player stats
        await self.handle_show_stats(channel, user)
        
        # Show inventory
        await self.handle_show_inventory(channel, user)
        
        # Show current quest progress
        async with await self.bot.db_connect() as db:
            cursor = await db.execute('''
                SELECT quest_id, objectives_progress FROM active_quests 
                WHERE player_id = ? AND completed = FALSE
                LIMIT 1
            ''', (user.id,))
            quest_data = await cursor.fetchone()
            
            if quest_data:
                quest_id, objectives_progress_json = quest_data
                quest = self.quest_manager.quests.get(quest_id)
                
                if quest:
                    import json
                    objectives_progress = json.loads(objectives_progress_json)
                    
                    embed = discord.Embed(
                        title="📜 Current Quest",
                        description=f"**{quest.title}**\n{quest.description}",
                        color=discord.Color.gold()
                    )
                    
                    # Show progress for each objective
                    progress_text = []
                    for i, obj in enumerate(quest.objectives):
                        current = objectives_progress[i] if i < len(objectives_progress) else 0
                        progress_text.append(f"{obj.description}: {current}/{obj.count}")
                    
                    embed.add_field(
                        name="Progress",
                        value="\n".join(progress_text),
                        inline=False
                    )
                    
                    await channel.send(embed=embed)
            else:
                await channel.send(f"{user.mention} You don't have an active quest. Use `!w quests` to view available quests.")
            
    async def process_combat_round(self, player, enemy, player_attack):
        """Process a round of combat and return the embed"""
        embed = discord.Embed(
            title="⚔️ Combat Round",
            color=discord.Color.blue()
        )
        
        # Player's turn
        result = player_attack.execute(player, enemy)
        if result['success']:
            embed.add_field(
                name="Your Attack",
                value=f"{result['message']}\nDamage: {result['damage']}",
                inline=False
            )
        else:
            embed.add_field(
                name="Your Attack",
                value=result['message'],
                inline=False
            )

            # Check if enemy is defeated
            if not enemy.is_alive():
                # Calculate XP gained (base 50 XP + 10 per enemy level)
                xp_gained = 50 + (enemy.level * 10)
                player.xp += xp_gained
                
                # Generate loot
                gold_dropped = random.randint(10 * enemy.level, 25 * enemy.level)
                possible_items = ["Health Potion", "Mana Potion", "Basic Sword", "Basic Staff", "Leather Armor"]
                dropped_items = []
                
                # 50% chance to drop an item
                if random.random() < 0.5:
                    dropped_items.append(random.choice(possible_items))
                
                # Check for level up
                leveled_up = player.xp >= player.xp_needed_for_next_level()
                if leveled_up:
                    player.level_up()

                # Create victory message
                loot_msg = f"🏆 You defeated {enemy.name}!\n"
                loot_msg += f"💰 Gold: {gold_dropped}\n"
                loot_msg += f"⭐ XP gained: {xp_gained}\n"
                if dropped_items:
                    loot_msg += f"📦 Items: {', '.join(dropped_items)}\n"
                if leveled_up:
                    loot_msg += f"🎉 Level Up! You are now level {player.level}!"

                embed.add_field(
                    name="Victory!",
                    value=loot_msg,
                    inline=False
                )            # Update database
            async with await self.bot.db_connect() as db:
                await db.execute('''
                    UPDATE players 
                    SET health = ?, mana = ?, xp = ?, level = ?, in_combat = FALSE, current_enemy = NULL
                    WHERE id = ?
                ''', (player.health, player.mana, player.xp, player.level, player.id))
                await db.commit()

            return embed

        # Enemy's turn
        player.regenerate_mana(0.2)  # Regenerate 20% mana
        
        # Enemy regenerates mana to sustain the fight
        if enemy.mana < enemy.max_mana:
            mana_regen = int(enemy.max_mana * 0.3)  # 30% mana regeneration per turn
            enemy.mana = min(enemy.max_mana, enemy.mana + mana_regen)
        
        enemy_attack = random.choice(enemy.attacks)
        enemy_result = enemy_attack.execute(enemy, player)

        if enemy_result['success']:
            embed.add_field(
                name="Enemy's Attack",
                value=f"{enemy_result['message']}\nDamage: {enemy_result['damage']}",
                inline=False
            )
        else:
            embed.add_field(
                name="Enemy's Attack",
                value=enemy_result['message'],
                inline=False
            )

        # Add current stats
        embed.add_field(
            name="Current Stats",
            value=f"You: {player.health}/{player.max_health} HP, {player.mana}/{player.max_mana} Mana\n" +
                  f"Enemy: {enemy.health}/{enemy.max_health} HP, {enemy.mana}/{enemy.max_mana} Mana",
            inline=False
        )

        # Check if player is defeated
        if not player.is_alive():
            embed.add_field(
                name="💀 Defeat!",
                value=f"You have died. Would you like to rest and play again?\n\n"
                      f"{self.RESTART_EMOJI} Rest and restart (penalty: 10% gold & XP)\n"
                      f"{self.LEAVE_EMOJI} Leave battle and view your status",
                inline=False
            )
            
            # Restore 50% health and reset combat
            player.health = player.max_health // 2
            player.mana = player.max_mana

            # Update database and increment deaths
            async with self.bot.db.execute('''
                UPDATE players 
                SET health = ?, mana = ?, in_combat = FALSE, current_enemy = NULL, deaths = deaths + 1
                WHERE id = ?
            ''', (player.health, player.mana, player.id)) as cursor:
                await self.bot.db.commit()
            
            # Return embed with defeat reactions flag
            embed.defeat_reactions = True
            return embed

        else:
            # Update database with current combat state
            async with self.bot.db.execute('''
                UPDATE players 
                SET health = ?, mana = ?
                WHERE id = ?
            ''', (player.health, player.mana, player.id)) as cursor:
                await self.bot.db.commit()

            # Add action buttons reminder
            embed.add_field(
                name="Actions",
                value=f"{self.MELEE_EMOJI} Melee Attack\n{self.MAGIC_EMOJI} Magic Attack\n{self.FLEE_EMOJI} Flee",
                inline=False
            )

        return embed
        
    async def start_combat(self, channel, user, enemy=None):
        """Start a combat encounter
        
        Args:
            channel: The discord channel to send messages to
            user: The discord user starting combat
            enemy: Optional pre-generated enemy (for quests)
        """
        logger.info(f"Starting combat for user {user.id}")
        if enemy:
            logger.info(f"Using pre-generated enemy: {enemy.name} (Level {enemy.level})")
        
        # Get player
        async with await self.bot.db_connect() as db:
            async with db.execute('SELECT * FROM players WHERE id = ?', (user.id,)) as cursor:
                if not (row := await cursor.fetchone()):
                    logger.warning(f"No character found for user {user.id}")
                    await channel.send(f"{user.mention} You need to create a character first! Use `!w start`")
                    return
                logger.info(f"Found character for user {user.id}: Level {row[2]}")
                
                # Display enemy stats
                # Display enemy stats and initiative roll
                initiative_embed = discord.Embed(
                    title="⚔️ Combat Initiative",
                    description="🎲 Rolling for initiative...",
                    color=discord.Color.blue()
                )
                initiative_msg = await channel.send(embed=initiative_embed)
                
                # Roll for initiative (50/50 chance)
                player_first = random.choice([True, False])
                await asyncio.sleep(1)  # Add a small delay for dramatic effect
                
                # Update initiative message
                initiative_embed.description = f"{'You' if player_first else enemy.name} won the initiative roll!"
                await initiative_msg.edit(embed=initiative_embed)
                await asyncio.sleep(1)  # Another small delay
                
                # Display enemy stats
                enemy_embed = discord.Embed(
                    title="⚔️ Enemy Stats",
                    description=f"You face a level {enemy.level} {enemy.name}!",
                    color=discord.Color.red()
                )
                enemy_embed.add_field(
                    name="Enemy Stats",
                    value=f"Health: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}",
                    inline=False
                )
                try:
                    await channel.send(embed=enemy_embed)
                    logger.info("Successfully sent enemy stats embed")
                except Exception as e:
                    logger.error(f"Failed to send enemy stats embed: {str(e)}")
                
                # If enemy goes first, process their attack
                if not player_first:
                    enemy_attack = random.choice(enemy.attacks)
                    enemy_result = enemy_attack.execute(enemy, player)
                    
                    # Send enemy attack result
                    attack_embed = discord.Embed(
                        title="Enemy Attack!",
                        description=f"{enemy.name} attacks first!",
                        color=discord.Color.red()
                    )
                    if enemy_result['success']:
                        attack_embed.add_field(
                            name="Attack Result",
                            value=f"{enemy_result['message']}\nDamage: {enemy_result['damage']}",
                            inline=False
                        )
                    else:
                        attack_embed.add_field(
                            name="Attack Result",
                            value=enemy_result['message'],
                            inline=False
                        )
                    await channel.send(embed=attack_embed)
                    
                    # Update database with player's new health
                    async with await self.bot.db_connect() as db:
                        await db.execute('''
                            UPDATE players 
                            SET health = ?
                            WHERE id = ?
                        ''', (player.health, player.id))
                        await db.commit()
                
                # Send combat options message
                options_embed = discord.Embed(
                    title="Your Turn",
                    description="Choose your action:",
                    color=discord.Color.blue()
                )
                options_embed.add_field(
                    name="Options",
                    value=f"{self.MELEE_EMOJI} Melee Attack\n{self.MAGIC_EMOJI} Magic Attack\n{self.FLEE_EMOJI} Flee",
                    inline=False
                )
                combat_msg = await channel.send(embed=options_embed)
                
                # Add reaction buttons
                for emoji in self.combat_emojis:
                    await combat_msg.add_reaction(emoji)
                
                # Store combat session
                self.active_combats[user.id] = {
                    'player': player,
                    'enemy': enemy,
                    'message_id': combat_msg.id,
                    'turn_history': []  # Track all combat turns
                }
                
                # Determine who goes first (50/50 chance)
                player_goes_first = random.choice([True, False])
                turn_message = discord.Embed(
                    title="Combat Initiative!",
                    description="🎲 Rolling for initiative...",
                    color=discord.Color.blue()
                )
                turn_msg = await channel.send(embed=turn_message)
                
                # Create the player object
                player = Player(
                    id=row[0],
                    name=row[1],
                    level=row[2],
                    xp=row[3],
                    health=row[4],
                    max_health=row[5],
                    mana=row[6],
                    max_mana=row[7]
                )

                if player.in_combat:
                    await channel.send(f"{user.mention} You're already in combat!")
                    return

            # If enemy wasn't provided, generate one
            if not enemy:
                enemy = self.enemy_generator.generate_enemy(player.level)
            player.current_enemy = enemy
            player.in_combat = True

            # Save initial combat state
            async with await self.bot.db_connect() as db:
                await db.execute('''
                    UPDATE players 
                    SET in_combat = ?, current_enemy = ?
                    WHERE id = ?
                ''', (True, enemy.name, player.id))
                await db.commit()

            # Update initiative message
            await turn_msg.edit(embed=discord.Embed(
                title="Combat Initiative!",
                description=f"{'You' if player_goes_first else enemy.name} won the initiative roll!",
                color=discord.Color.blue()
            ))

            # Create combat embed
            embed = discord.Embed(
                title="⚔️ Combat Started!",
                description=f"Combat with {enemy.name} (Level {enemy.level}) has begun!",
                color=discord.Color.red()
            )

            # If enemy goes first, process their attack
            if not player_goes_first:
                enemy_attack = random.choice(enemy.attacks)
                enemy_result = enemy_attack.execute(enemy, player)
                
                # Update player health in database
                async with await self.bot.db_connect() as db:
                    await db.execute('''
                        UPDATE players 
                        SET health = ?
                        WHERE id = ?
                    ''', (player.health, player.id))
                    await db.commit()

                if enemy_result['success']:
                    embed.add_field(
                        name=f"{enemy.name} Attacks First!",
                        value=f"{enemy_result['message']}\nDamage: {enemy_result['damage']}",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name=f"{enemy.name} Attacks First!",
                        value=enemy_result['message'],
                        inline=False
                    )

            # Add current stats
            embed.add_field(
                name=f"{enemy.name}'s Stats",
                value=f"Health: {enemy.health}/{enemy.max_health}\nMana: {enemy.mana}/{enemy.max_mana}",
                inline=False
            )
            embed.add_field(
                name="Your Stats",
                value=f"Health: {player.health}/{player.max_health}\nMana: {player.mana}/{player.max_mana}",
                inline=False
            )
            embed.add_field(
                name="Actions",
                value=f"{self.MELEE_EMOJI} Melee Attack\n{self.MAGIC_EMOJI} Magic Attack\n{self.FLEE_EMOJI} Flee",
                inline=False
            )

            combat_message = await channel.send(embed=embed)
            
            # Add reaction buttons
            for emoji in self.combat_emojis:
                await combat_message.add_reaction(emoji)

            # Store combat message ID for reaction handling
            self.active_combats[user.id] = {
                'message_id': combat_message.id,
                'player': player,
                'enemy': enemy,
                'turn_history': []  # Track all combat turns
            }

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle combat reactions"""
        logger.info(f"Combat: Reaction received - Emoji: {reaction.emoji}, User ID: {user.id}, Message ID: {reaction.message.id}")
        
        if user.bot:
            logger.debug("Combat: Ignoring bot reaction")
            return

        # Get bot's permissions in the channel
        bot_permissions = reaction.message.channel.permissions_for(reaction.message.guild.me)
        if not (bot_permissions.manage_messages and bot_permissions.send_messages):
            logger.warning(f"Bot lacks required permissions in channel {reaction.message.channel.id}")
            return

        # Check for victory message reactions
        victory_data = self.victory_messages.get(user.id)
        logger.info(f"Checking victory message for user {user.id}: victory_data={victory_data}, message_id={reaction.message.id}")
        if victory_data and reaction.message.id == victory_data['message_id']:
            logger.info(f"Handling victory action for user {user.id}")
            await self.handle_victory_action(reaction, user)
            return

        # Check if user is already in combat FIRST
        combat_data = self.active_combats.get(user.id)
        if combat_data:
            # Handle combat actions for active combat
            if reaction.message.id == combat_data['message_id']:
                logger.info(f"Processing combat action for user {user.id}")
                attack_type = None
                if str(reaction.emoji) == self.MELEE_EMOJI:
                    attack_type = "melee"
                elif str(reaction.emoji) == self.MAGIC_EMOJI:
                    attack_type = "magic"
                elif str(reaction.emoji) == self.ITEM_EMOJI:
                    await self.handle_item_usage(reaction.message.channel, user, combat_data)
                    return
                elif str(reaction.emoji) == self.PRAY_EMOJI:
                    await self.handle_pray(reaction.message.channel, user.id)
                    return
                elif str(reaction.emoji) == self.FLEE_EMOJI:
                    await self.handle_flee(reaction.message.channel, user, combat_data)
                    return
                
                if attack_type:
                    await self.handle_combat_round(reaction.message.channel, user.id, attack_type)
                    
                # Remove reaction
                try:
                    await reaction.remove(user)
                except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
                    logger.warning(f"Could not remove reaction: {str(e)}")
            return
        
        # Only start new combat if NOT already in combat
        if str(reaction.emoji) == "⚔️":
            logger.info(f"Combat start emoji detected for user {user.id}")
            try:
                # Start quest combat directly
                await self.start_quest_combat(reaction.message.channel, user.id)
                logger.info(f"Combat started successfully for user {user.id}")

                # Remove the start reaction
                try:
                    await reaction.remove(user)
                except (discord.Forbidden, discord.NotFound, discord.HTTPException) as e:
                    logger.warning(f"Could not remove reaction: {str(e)}")
                return
            except Exception as e:
                logger.error(f"Error starting combat: {str(e)}")
                await reaction.message.channel.send("There was an error starting combat. Please try again.")
                return
                    
                # Remove the reaction
                try:
                    await reaction.remove(user)
                except:
                    pass
            return
            
        # Check if this is a combat start reaction
        if str(reaction.emoji) == "⚔️":
            logger.info(f"Combat start emoji detected for user {user.id}")
            try:
                # Start quest combat directly
                await self.start_quest_combat(reaction.message.channel, user.id)
                logger.info(f"Combat started successfully for user {user.id}")
                
                # Remove the start reaction
                try:
                    await reaction.remove(user)
                except:
                    pass
            except Exception as e:
                logger.error(f"Error starting combat: {str(e)}")
                await reaction.message.channel.send("There was an error starting combat. Please try again.")
            
        # Check if this is the initial combat start reaction
        if str(reaction.emoji) == self.MELEE_EMOJI:
            logger.info(f"Combat start emoji detected for user {user.id}")
            async with await self.bot.db_connect() as db:
                cursor = await db.execute('SELECT * FROM players WHERE id = ?', (user.id,))
                player_data = await cursor.fetchone()
                if player_data:
                    logger.info(f"Found player data for user {user.id}")
                    await self.start_quest_combat(reaction.message.channel, user.id)
                    return
                else:
                    logger.warning(f"No player data found for user {user.id}")

        combat_data = self.active_combats.get(user.id)
        logger.info(f"Combat data for user {user.id}: {combat_data is not None}")
        
        if not combat_data:
            logger.info(f"No combat data found for user {user.id}")
            return
            
        if reaction.message.id != combat_data['message_id']:
            logger.info(f"Message ID mismatch - Expected: {combat_data['message_id']}, Got: {reaction.message.id}")
            return

        player = combat_data['player']
        enemy = combat_data['enemy']
        logger.info(f"Combat validated - Player: {player.name}, Enemy: {enemy.name}")

        # Remove user's reaction
        await reaction.remove(user)

        # Handle different combat actions
        attack_type = None
        if str(reaction.emoji) == self.MELEE_EMOJI:
            attack_type = 'melee'
        elif str(reaction.emoji) == self.MAGIC_EMOJI:
            attack_type = 'magic'
        elif str(reaction.emoji) == self.FLEE_EMOJI:
            await self.handle_flee(reaction.message.channel, user, combat_data)
            return

        # Get player
        channel = reaction.message.channel
        async with await self.bot.db_connect() as db:
            async with db.execute('SELECT * FROM players WHERE id = ?', (user.id,)) as cursor:
                if not (row := await cursor.fetchone()):
                    await channel.send(f"{user.mention} You need to create a character first! Use `!w start`")
                    return

                player = Player(
                    id=row[0],
                    name=row[1],
                    level=row[2],
                    xp=row[3],
                health=row[4],
                max_health=row[5],
                mana=row[6],
                max_mana=row[7]
            )

            if not player.in_combat or not player.current_enemy:
                await channel.send(f"{user.mention} You're not in combat! Use `!w fight` to start a fight")
                return

            # Player's turn
            attack = next((a for a in player.basic_attacks if a.attack_type == attack_type), None)
            if not attack:
                await channel.send(f"{user.mention} No {attack_type} attack available!")
                return

            result = attack.execute(player, player.current_enemy)
            
            embed = discord.Embed(
                title="⚔️ Combat Round",
                color=discord.Color.blue()
            )
            
            if result['success']:
                embed.add_field(
                    name="Your Attack",
                    value=f"{result['message']}\nDamage: {result['damage']}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Your Attack",
                    value=result['message'],
                    inline=False
                )

            # Check if enemy is defeated
            if not player.current_enemy.is_alive():
                # Calculate XP gained (base 50 XP + 10 per enemy level)
                xp_gained = 50 + (player.current_enemy.level * 10)
                player.xp += xp_gained
                
                # Check for level up
                leveled_up = player.xp >= player.xp_needed_for_next_level()
                if leveled_up:
                    player.level_up()

                embed.add_field(
                    name="Victory!",
                    value=f"You defeated {player.current_enemy.name}!\nXP gained: {xp_gained}" + 
                          (f"\n🎉 Level Up! You are now level {player.level}!" if leveled_up else ""),
                    inline=False
                )

                # Reset combat state
                player.in_combat = False
                player.current_enemy = None

                # Save player state
                async with await self.bot.db_connect() as db:
                    await db.execute('''
                        UPDATE players 
                        SET health = ?, mana = ?, xp = ?, level = ?, in_combat = ?, current_enemy = NULL
                        WHERE id = ?
                    ''', (player.health, player.mana, player.xp, player.level, False, player.id))
                    await db.commit()

                await channel.send(embed=embed)
                return

            # Enemy's turn
            player.regenerate_mana(0.2)  # Regenerate 20% mana
            
            # Enemy regenerates mana to sustain the fight
            if player.current_enemy.mana < player.current_enemy.max_mana:
                mana_regen = int(player.current_enemy.max_mana * 0.3)  # 30% mana regeneration per turn
                player.current_enemy.mana = min(player.current_enemy.max_mana, player.current_enemy.mana + mana_regen)
            
            enemy_attack = random.choice(player.current_enemy.attacks)
            enemy_result = enemy_attack.execute(player.current_enemy, player)

            if enemy_result['success']:
                embed.add_field(
                    name="Enemy's Attack",
                    value=f"{enemy_result['message']}\nDamage: {enemy_result['damage']}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Enemy's Attack",
                    value=enemy_result['message'],
                    inline=False
                )

            # Add current stats
            embed.add_field(
                name="Current Stats",
                value=f"You: {player.health}/{player.max_health} HP, {player.mana}/{player.max_mana} Mana\n" +
                      f"Enemy: {player.current_enemy.health}/{player.current_enemy.max_health} HP, {player.current_enemy.mana}/{player.current_enemy.max_mana} Mana",
                inline=False
            )

            # Check if player is defeated
            if not player.is_alive():
                embed.add_field(
                    name="💀 Defeat!",
                    value=f"You have died. Would you like to rest and play again?\n\n"
                          f"{self.RESTART_EMOJI} Rest and restart (penalty: 10% gold & XP)\n"
                          f"{self.LEAVE_EMOJI} Leave battle and view your status",
                    inline=False
                )
                
                # Restore 50% health and reset combat
                player.health = player.max_health // 2
                player.mana = player.max_mana
                player.in_combat = False
                player.current_enemy = None

            # Save player state and increment deaths if defeated
            async with await self.bot.db_connect() as db:
                if not player.is_alive():
                    await db.execute('''
                        UPDATE players 
                        SET health = ?, mana = ?, in_combat = ?, current_enemy = ?, deaths = deaths + 1
                        WHERE id = ?
                    ''', (
                        player.health,
                        player.mana,
                        player.in_combat,
                        player.current_enemy.name if player.current_enemy else None,
                        player.id
                    ))
                else:
                    await db.execute('''
                        UPDATE players 
                        SET health = ?, mana = ?, in_combat = ?, current_enemy = ?
                        WHERE id = ?
                    ''', (
                        player.health,
                        player.mana,
                        player.in_combat,
                        player.current_enemy.name if player.current_enemy else None,
                        player.id
                    ))
                await db.commit()

            defeat_msg = await reaction.message.channel.send(embed=embed)
            
            # Add defeat reactions if player was defeated
            if not player.is_alive() or player.health <= player.max_health // 2:
                for emoji in self.defeat_emojis:
                    await defeat_msg.add_reaction(emoji)
                
                # Store defeat message for reaction handling
                self.victory_messages[user.id] = {
                    'message_id': defeat_msg.id,
                    'type': 'defeat',
                    'player': player
                }

async def setup(bot):
    await bot.add_cog(CombatCommands(bot))