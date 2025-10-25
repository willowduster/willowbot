import discord
from discord.ext import commands
from src.models.player import Player
from src.models.quest_manager import QuestManager
import aiosqlite
import os
import logging

logger = logging.getLogger(__name__)

class PlayerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Remove default help command so we can override it
        self.bot.remove_command('help')
        self.help_pages = {}
    
    async def get_player(self, user_id: int, ctx=None) -> Player:
        """Get a player by ID, creating them if they don't exist"""
        async with await self.bot.db_connect() as db:
            async with db.execute('SELECT * FROM players WHERE id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                if row is None and ctx:
                    # Create new player
                    name = ctx.author.display_name
                    await db.execute('''
                        INSERT INTO players (id, name, level, xp, health, max_health, mana, max_mana)
                        VALUES (?, ?, 1, 0, 100, 100, 100, 100)
                    ''', (user_id, name))
                    
                    # Give starting items: 3 mana potions
                    await db.execute('''
                        INSERT INTO inventory (player_id, item_id, count)
                        VALUES (?, 'mana_potion', 3)
                    ''', (user_id,))
                    
                    await db.commit()
                    
                    # Start the first quest automatically
                    quest_manager = QuestManager(self.bot)
                    first_quest = await quest_manager.start_quest(user_id, 'quest_1_1')
                    if first_quest:
                        logger.info(f"Auto-started quest_1_1 for new player {user_id}")
                    
                    return await self.get_player(user_id)
                elif row:
                    return Player(
                        id=row[0],
                        name=row[1],
                        level=row[2],
                        xp=row[3],
                        health=row[4],
                        max_health=row[5],
                        mana=row[6],
                        max_mana=row[7]
                    )
                return None

    async def save_player(self, player: Player):
        async with aiosqlite.connect(self.bot.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO players 
                (id, name, level, xp, health, max_health, mana, max_mana)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                player.id,
                player.name,
                player.level,
                player.xp,
                player.health,
                player.max_health,
                player.mana,
                player.max_mana
            ))
            await db.commit()

    @commands.command(name='start')
    async def start(self, ctx):
        """Start your adventure!"""
        if await self.get_player(ctx.author.id):
            await ctx.send("You already have a character!")
            return
        
        player = Player(
            id=ctx.author.id,
            name=ctx.author.name
        )
        await self.save_player(player)
        
        # Start the first quest automatically
        quest_manager = QuestManager(self.bot)
        first_quest = await quest_manager.start_quest(ctx.author.id, 'quest_1_1')
        
        embed = discord.Embed(
            title="Welcome to the Adventure!",
            description=f"Character created for {ctx.author.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Level", value=player.level)
        embed.add_field(name="Health", value=f"{player.health}/{player.max_health}")
        embed.add_field(name="Mana", value=f"{player.mana}/{player.max_mana}")
        embed.add_field(name="XP", value=f"{player.xp}/{player.xp_needed_for_next_level()}")
        
        if first_quest:
            embed.add_field(
                name="🎯 First Quest Started!",
                value=f"**{first_quest.title}**\n{first_quest.description}\n\nStarting your first battle...",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
        # Auto-start combat for the first quest
        if first_quest:
            combat_cog = self.bot.get_cog('CombatCommands')
            if combat_cog:
                try:
                    await combat_cog.start_quest_combat(ctx.channel, ctx.author.id)
                    logger.info(f"Auto-started combat for new player {ctx.author.id}")
                except Exception as e:
                    logger.error(f"Failed to auto-start combat: {e}", exc_info=True)
                    await ctx.send("Use `!w quests` to begin your first quest!")

    @commands.command(name='stats', aliases=['s'])
    async def stats(self, ctx):
        """View your character stats"""
        if player := await self.get_player(ctx.author.id, ctx):
            # Get deaths and kills from database
            async with await self.bot.db_connect() as db:
                cursor = await db.execute('SELECT deaths FROM players WHERE id = ?', (ctx.author.id,))
                deaths_row = await cursor.fetchone()
                deaths = deaths_row[0] if deaths_row else 0
                
                cursor = await db.execute('SELECT COUNT(*) FROM player_kills WHERE player_id = ?', (ctx.author.id,))
                kills_row = await cursor.fetchone()
                kills = kills_row[0] if kills_row else 0
            
            embed = discord.Embed(
                title=f"{player.name}'s Stats",
                color=discord.Color.blue()
            )
            embed.add_field(name="Level", value=player.level, inline=True)
            embed.add_field(name="Health", value=f"{player.health}/{player.max_health}", inline=True)
            embed.add_field(name="Mana", value=f"{player.mana}/{player.max_mana}", inline=True)
            embed.add_field(name="XP", value=f"{player.xp}/{player.xp_needed_for_next_level()}", inline=True)
            embed.add_field(name="💀 Deaths", value=deaths, inline=True)
            embed.add_field(name="⚔️ Kills", value=kills, inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send("You haven't started your adventure yet! Use `!w start` to begin!")

    @commands.command(name='help', aliases=['h', 'commands'])
    async def help(self, ctx):
        """Show help information with quick action button"""
        # Check if player exists
        player = await self.get_player(ctx.author.id)
        
        embed = discord.Embed(
            title="🎮 WillowBot",
            description="A Discord RPG Adventure",
            color=discord.Color.blue()
        )
        
        if player:
            # Existing player - show them how to continue
            embed.add_field(
                name="Welcome back!",
                value="Click **▶️ Start Playing** below to continue your adventure!",
                inline=False
            )
            embed.set_footer(text="▶️ Start Playing")
        else:
            # New player - show them how to start
            embed.add_field(
                name="Welcome, adventurer!",
                value="Click **▶️ Start Playing** below to create your character and begin your quest!",
                inline=False
            )
            embed.set_footer(text="▶️ Start Playing")
        
        message = await ctx.send(embed=embed)
        
        # Store for reaction handling
        self.help_pages[ctx.author.id] = {
            'message_id': message.id,
            'has_player': player is not None
        }
        
        # Add start button
        await message.add_reaction("▶️")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle help navigation via reactions"""
        if user.bot:
            return

        message = reaction.message
        
        # Check if this is a help message we're tracking
        if user.id not in self.help_pages or self.help_pages[user.id].get('message_id') != message.id:
            return

        # Try to remove user's reaction if we have permission
        try:
            await reaction.remove(user)
        except (discord.Forbidden, discord.HTTPException):
            pass  # Bot doesn't have permission or other error

        emoji = str(reaction.emoji)
        user_help = self.help_pages[user.id]

        if emoji == "▶️":  # Start Playing
            # Delete help message
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            del self.help_pages[user.id]
            
            if user_help['has_player']:
                # Existing player - show quests
                quest_cog = self.bot.get_cog('QuestCommands')
                if quest_cog:
                    ctx = await self.bot.get_context(message)
                    ctx.author = user
                    await quest_cog.list_quests(ctx)
                else:
                    await message.channel.send("Quest system is currently unavailable.")
            else:
                # New player - create character
                ctx = await self.bot.get_context(message)
                ctx.author = user
                await self.start(ctx)
            return

async def setup(bot):
    await bot.add_cog(PlayerCommands(bot))