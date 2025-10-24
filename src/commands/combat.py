import discord
from discord.ext import commands
from ..models.player import Player
from ..models.enemy import EnemyGenerator
from ..models.combat import Attack, CombatEntity
import random

class CombatCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.enemy_generator = EnemyGenerator()
        # Track active combat sessions
        self.active_combats = {}
        # Reaction emojis for combat actions
        self.MELEE_EMOJI = "⚔️"
        self.MAGIC_EMOJI = "🔮"
        self.FLEE_EMOJI = "🏃"
        self.combat_emojis = [self.MELEE_EMOJI, self.MAGIC_EMOJI, self.FLEE_EMOJI]
        
    async def handle_combat_round(self, channel, user_id: int, attack_type: str):
        """Handle a round of combat"""
        combat_data = self.active_combats.get(user_id)
        if not combat_data:
            return
            
        player = combat_data['player']
        enemy = combat_data['enemy']
        
        # Get the appropriate attack
        attack = next((a for a in player.basic_attacks if a.attack_type == attack_type), None)
        if not attack:
            await channel.send(f"No {attack_type} attack available!")
            return
            
        # Create combat round embed
        embed = await self.process_combat_round(player, enemy, attack)
        
        # Update or end combat
        if not player.is_alive() or not enemy.is_alive():
            # Clean up combat session
            del self.active_combats[user_id]
            # Remove reactions from the message
            message = await channel.fetch_message(combat_data['message_id'])
            await message.clear_reactions()
        else:
            # Add fresh reactions for next round
            message = await channel.fetch_message(combat_data['message_id'])
            await message.clear_reactions()
            for emoji in self.combat_emojis:
                await message.add_reaction(emoji)
                
        await channel.send(embed=embed)
        
    async def handle_flee(self, channel, user, combat_data):
        """Handle flee attempt"""
        if random.random() < 0.5:
            # Successful flee
            del self.active_combats[user.id]
            message = await channel.fetch_message(combat_data['message_id'])
            await message.clear_reactions()
            await channel.send(f"{user.mention} successfully fled from combat!")
        else:
            await channel.send(f"{user.mention} failed to flee! The enemy blocks your escape!")
            
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
            
            # Check for level up
            leveled_up = player.xp >= player.xp_needed_for_next_level()
            if leveled_up:
                player.level_up()

            embed.add_field(
                name="Victory!",
                value=f"You defeated {enemy.name}!\nXP gained: {xp_gained}" + 
                      (f"\n🎉 Level Up! You are now level {player.level}!" if leveled_up else ""),
                inline=False
            )

            # Update database
            async with self.bot.db.execute('''
                UPDATE players 
                SET health = ?, mana = ?, xp = ?, level = ?, in_combat = FALSE, current_enemy = NULL
                WHERE id = ?
            ''', (player.health, player.mana, player.xp, player.level, player.id)) as cursor:
                await self.bot.db.commit()

            return embed

        # Enemy's turn
        player.regenerate_mana(0.2)  # Regenerate 20% mana
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
                name="Defeat!",
                value="You have been defeated! Your health has been restored to 50%.",
                inline=False
            )
            
            # Restore 50% health and reset combat
            player.health = player.max_health // 2
            player.mana = player.max_mana

            # Update database
            async with self.bot.db.execute('''
                UPDATE players 
                SET health = ?, mana = ?, in_combat = FALSE, current_enemy = NULL
                WHERE id = ?
            ''', (player.health, player.mana, player.id)) as cursor:
                await self.bot.db.commit()

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
        
    async def start_combat(self, ctx, enemy_level: int = None):
        """Start a combat encounter (called by quest system)"""
        # Get player
        async with self.bot.db.execute('SELECT * FROM players WHERE id = ?', (ctx.author.id,)) as cursor:
            if not (row := await cursor.fetchone()):
                await ctx.send("You need to create a character first! Use `!wb start`")
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

            if player.in_combat:
                await ctx.send("You're already in combat!")
                return

            # Generate enemy
            enemy = self.enemy_generator.generate_enemy(player.level)
            player.current_enemy = enemy
            player.in_combat = True

            # Save player state
            await self.bot.db.execute('''
                UPDATE players 
                SET in_combat = ?, current_enemy = ?
                WHERE id = ?
            ''', (True, enemy.name, player.id))
            await self.bot.db.commit()

            # Create embed for combat start
            embed = discord.Embed(
                title="⚔️ Combat Started!",
                description=f"You encountered a {enemy.name} (Level {enemy.level})!",
                color=discord.Color.red()
            )
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

            combat_message = await ctx.send(embed=embed)
            
            # Add reaction buttons
            for emoji in self.combat_emojis:
                await combat_message.add_reaction(emoji)
                
            def check(reaction, user):
                return (
                    user == ctx.author 
                    and str(reaction.emoji) in self.combat_emojis 
                    and reaction.message.id == combat_message.id
                )

            # Store combat message ID for reaction handling
            self.active_combats[ctx.author.id] = {
                'message_id': combat_message.id,
                'player': player,
                'enemy': enemy
            }

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle combat reactions"""
        if user.bot:
            return

        combat_data = self.active_combats.get(user.id)
        if not combat_data or reaction.message.id != combat_data['message_id']:
            return

        player = combat_data['player']
        enemy = combat_data['enemy']

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
        async with self.bot.db.execute('SELECT * FROM players WHERE id = ?', (ctx.author.id,)) as cursor:
            if not (row := await cursor.fetchone()):
                await ctx.send("You need to create a character first! Use `!wb start`")
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
                await ctx.send("You're not in combat! Use `!wb fight` to start a fight")
                return

            # Player's turn
            attack = next((a for a in player.basic_attacks if a.attack_type == attack_type), None)
            if not attack:
                await ctx.send(f"No {attack_type} attack available!")
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
                await self.bot.db.execute('''
                    UPDATE players 
                    SET health = ?, mana = ?, xp = ?, level = ?, in_combat = ?, current_enemy = NULL
                    WHERE id = ?
                ''', (player.health, player.mana, player.xp, player.level, False, player.id))
                await self.bot.db.commit()

                await ctx.send(embed=embed)
                return

            # Enemy's turn
            player.regenerate_mana(0.2)  # Regenerate 20% mana
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
                    name="Defeat!",
                    value="You have been defeated! Your health has been restored to 50%.",
                    inline=False
                )
                
                # Restore 50% health and reset combat
                player.health = player.max_health // 2
                player.mana = player.max_mana
                player.in_combat = False
                player.current_enemy = None

            # Save player state
            await self.bot.db.execute('''
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
            await self.bot.db.commit()

            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(CombatCommands(bot))