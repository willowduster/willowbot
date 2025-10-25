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
        # Remove default help command so we can override it
        self.bot.remove_command('help')
    
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
        """Show help information with reaction navigation"""
        pages = []
        
        # Page 1: Getting Started
        embed1 = discord.Embed(
            title="🎮 WillowBot - Getting Started",
            description="Welcome to WillowBot! A Discord RPG adventure.",
            color=discord.Color.blue()
        )
        embed1.add_field(
            name="🌟 Start Your Adventure",
            value="`!w start` - Create your character and begin!",
            inline=False
        )
        embed1.add_field(
            name="📊 Check Your Stats",
            value="`!w stats` or `!w s` - View your character stats, level, HP, mana, kills, and deaths",
            inline=False
        )
        embed1.add_field(
            name="💡 Quick Tip",
            value="React with ➡️ to see more commands!",
            inline=False
        )
        embed1.set_footer(text="Page 1/4 • Use ➡️ and ⬅️ to navigate • ❌ to close")
        pages.append(embed1)
        
        # Page 2: Quests & Combat
        embed2 = discord.Embed(
            title="⚔️ WillowBot - Quests & Combat",
            description="Embark on quests and fight enemies!",
            color=discord.Color.red()
        )
        embed2.add_field(
            name="📜 View Quests",
            value="`!w quests` or `!w q` - Browse available quests with reaction controls",
            inline=False
        )
        embed2.add_field(
            name="📋 Quest Progress",
            value="`!w quest_progress` - Check your current quest progress",
            inline=False
        )
        embed2.add_field(
            name="⚔️ Combat Actions (React to combat messages)",
            value=(
                "⚔️ - Melee attack\n"
                "🔮 - Magic attack\n"
                "🧪 - Use potion\n"
                "🙏 - Pray (restore mana)\n"
                "🏃 - Flee from combat"
            ),
            inline=False
        )
        embed2.add_field(
            name="💡 Combat Tip",
            value="After victory or fleeing, use 🛏️ to rest and restore HP/Mana!",
            inline=False
        )
        embed2.set_footer(text="Page 2/4 • Use ➡️ and ⬅️ to navigate • ❌ to close")
        pages.append(embed2)
        
        # Page 3: Inventory & Equipment
        embed3 = discord.Embed(
            title="🎒 WillowBot - Inventory & Equipment",
            description="Manage your items and equipment!",
            color=discord.Color.green()
        )
        embed3.add_field(
            name="🎒 View Inventory",
            value="`!w inventory` or `!w inv` - See all your items",
            inline=False
        )
        embed3.add_field(
            name="🛡️ View Equipment",
            value="`!w equipment` or `!w equip` - See equipped items and stats",
            inline=False
        )
        embed3.add_field(
            name="🔍 Item Details",
            value="`!w item <item_name>` - Get detailed info about an item",
            inline=False
        )
        embed3.add_field(
            name="🧪 Use Items",
            value="`!w use <item_name>` - Use consumable items (potions, etc.)",
            inline=False
        )
        embed3.add_field(
            name="💡 Equipment Tip",
            value="Equipment automatically boosts your stats when equipped!",
            inline=False
        )
        embed3.set_footer(text="Page 3/4 • Use ➡️ and ⬅️ to navigate • ❌ to close")
        pages.append(embed3)
        
        # Page 4: Tips & Tricks
        embed4 = discord.Embed(
            title="💡 WillowBot - Tips & Tricks",
            description="Pro tips to help you succeed!",
            color=discord.Color.gold()
        )
        embed4.add_field(
            name="⚡ Level Up",
            value="Earn XP from combat to level up! XP carries over when you level up.",
            inline=False
        )
        embed4.add_field(
            name="🙏 Prayer",
            value="No mana potions? Use the 🙏 Pray action in combat to restore 20-40% mana!",
            inline=False
        )
        embed4.add_field(
            name="🏃 Fleeing",
            value="Successfully flee from tough battles! You can rest, retry, or check your inventory after fleeing.",
            inline=False
        )
        embed4.add_field(
            name="📈 Quest Chains",
            value="Complete quests in sequence to unlock new challenges and better rewards!",
            inline=False
        )
        embed4.add_field(
            name="💀 Death Penalty",
            value="Death costs 10% of your gold and XP, but you can retry immediately!",
            inline=False
        )
        embed4.add_field(
            name="🌐 Web Dashboard",
            value="Visit http://localhost:5000 to view detailed stats and leaderboards!",
            inline=False
        )
        embed4.set_footer(text="Page 4/4 • Use ➡️ and ⬅️ to navigate • ❌ to close")
        pages.append(embed4)
        
        # Send first page
        message = await ctx.send(embed=pages[0])
        
        # Store pages for this user
        self.help_pages[ctx.author.id] = {
            'pages': pages,
            'current_page': 0,
            'message_id': message.id
        }
        
        # Add navigation reactions
        await message.add_reaction("⬅️")
        await message.add_reaction("➡️")
        await message.add_reaction("❌")

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
        pages = user_help['pages']
        current_page = user_help['current_page']

        if emoji == "➡️":  # Next page
            current_page = (current_page + 1) % len(pages)
        elif emoji == "⬅️":  # Previous page
            current_page = (current_page - 1) % len(pages)
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

        # Update page and edit message
        user_help['current_page'] = current_page
        await message.edit(embed=pages[current_page])

async def setup(bot):
    await bot.add_cog(PlayerCommands(bot))