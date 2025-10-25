import discord
from discord.ext import commands
from src.models.player import Player
import aiosqlite
import os

class PlayerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Remove default help command so we can override it
        self.bot.remove_command('help')
        self.help_pages = {}
    
    async def setup_database(self):
        async with await self.bot.db_connect() as db:
            # Players table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    level INTEGER,
                    xp INTEGER,
                    health INTEGER,
                    max_health INTEGER,
                    mana INTEGER,
                    max_mana INTEGER,
                    in_combat BOOLEAN DEFAULT FALSE,
                    current_enemy TEXT DEFAULT NULL,
                    gold INTEGER DEFAULT 0,
                    current_title TEXT DEFAULT NULL
                )
            ''')

            # Active quests table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS active_quests (
                    player_id INTEGER,
                    quest_id TEXT,
                    completed BOOLEAN DEFAULT FALSE,
                    rewards_claimed BOOLEAN DEFAULT FALSE,
                    objectives_progress TEXT,  -- JSON string of objective progress
                    FOREIGN KEY (player_id) REFERENCES players(id),
                    PRIMARY KEY (player_id, quest_id)
                )
            ''')

            # Completed quest chains table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS completed_quest_chains (
                    player_id INTEGER,
                    chain_id TEXT,
                    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (player_id) REFERENCES players(id),
                    PRIMARY KEY (player_id, chain_id)
                )
            ''')

            # Inventory table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS inventory (
                    player_id INTEGER,
                    item_id TEXT,
                    count INTEGER DEFAULT 0,
                    FOREIGN KEY (player_id) REFERENCES players(id),
                    PRIMARY KEY (player_id, item_id)
                )
            ''')

            # Player titles table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_titles (
                    player_id INTEGER,
                    title_id TEXT,
                    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (player_id) REFERENCES players(id),
                    PRIMARY KEY (player_id, title_id)
                )
            ''')

            await db.commit()
    
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
        
        embed = discord.Embed(
            title="Welcome to the Adventure!",
            description=f"Character created for {ctx.author.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Level", value=player.level)
        embed.add_field(name="Health", value=f"{player.health}/{player.max_health}")
        embed.add_field(name="Mana", value=f"{player.mana}/{player.max_mana}")
        embed.add_field(name="XP", value=f"{player.xp}/{player.xp_needed_for_next_level()}")
        
        await ctx.send(embed=embed)

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
        """Show help information with quick action buttons"""
        # Check if player exists
        player = await self.get_player(ctx.author.id)
        
        embed = discord.Embed(
            title="🎮 WillowBot - Discord RPG Adventure",
            description="Welcome to WillowBot! Fight enemies, complete quests, and level up!",
            color=discord.Color.blue()
        )
        
        # Getting Started section
        embed.add_field(
            name="🌟 Getting Started",
            value=(
                "`!w start` - Create your character\n"
                "`!w stats` or `!w s` - View your stats\n"
                "`!w help` or `!w h` - Show this help"
            ),
            inline=False
        )
        
        # Quests & Combat section
        embed.add_field(
            name="⚔️ Quests & Combat",
            value=(
                "`!w quests` or `!w q` - Browse quests\n"
                "`!w quest_progress` - Check progress\n"
                "\n**Combat Actions (React to messages):**\n"
                "⚔️ Melee • 🔮 Magic • 🧪 Potion\n"
                "🙏 Pray • 🏃 Flee • 🛏️ Rest"
            ),
            inline=False
        )
        
        # Inventory & Equipment section
        embed.add_field(
            name="🎒 Inventory & Items",
            value=(
                "`!w inventory` or `!w inv` - View items\n"
                "`!w equipment` or `!w equip` - View gear\n"
                "`!w item <name>` - Item details\n"
                "`!w use <name>` - Use consumables"
            ),
            inline=False
        )
        
        # Tips section
        embed.add_field(
            name="💡 Quick Tips",
            value=(
                "🙏 **Prayer** restores 20-40% mana when you have no potions\n"
                "⚡ **XP and loot** is awarded after each battle\n"
                "💀 **Death penalty** is 10% gold/XP but you can retry instantly"
            ),
            inline=False
        )
        
        # Add appropriate footer based on player status
        if player:
            embed.set_footer(text="� Continue Playing | ❌ Close • Click 🎯 to see your quests!")
        else:
            embed.set_footer(text="▶️ Start Adventure | ❌ Close")
        
        message = await ctx.send(embed=embed)
        
        # Store for reaction handling
        self.help_pages[ctx.author.id] = {
            'message_id': message.id,
            'has_player': player is not None
        }
        
        # Add appropriate reactions based on player status
        if player:
            await message.add_reaction("🎯")  # Continue playing (show quests)
        else:
            await message.add_reaction("▶️")  # Start adventure
        await message.add_reaction("❌")  # Close

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

        if emoji == "▶️":  # Start adventure
            # Delete help message
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            del self.help_pages[user.id]
            
            # Call start command
            ctx = await self.bot.get_context(message)
            ctx.author = user
            await self.start(ctx)
            return
            
        elif emoji == "🎯":  # Continue playing (show quests)
            # Delete help message
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass
            del self.help_pages[user.id]
            
            # Show quests
            quest_cog = self.bot.get_cog('QuestCommands')
            if quest_cog:
                ctx = await self.bot.get_context(message)
                ctx.author = user
                await quest_cog.list_quests(ctx)
            else:
                await message.channel.send("Quest system is currently unavailable.")
            return
            
        elif emoji == "❌":  # Close help
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                try:
                    # If we can't delete, edit to show it's closed
                    close_embed = discord.Embed(
                        title="Help Closed",
                        description="This help menu has been closed.",
                        color=discord.Color.dark_grey()
                    )
                    await message.edit(embed=close_embed)
                    await message.clear_reactions()
                except (discord.Forbidden, discord.NotFound):
                    pass
            del self.help_pages[user.id]
            return

async def setup(bot):
    await bot.add_cog(PlayerCommands(bot))