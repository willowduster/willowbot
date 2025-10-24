import discord
from discord.ext import commands
from src.models.player import Player
import aiosqlite
import os

class PlayerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
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
        async with aiosqlite.connect(self.db_path) as db:
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
            embed = discord.Embed(
                title=f"{player.name}'s Stats",
                color=discord.Color.blue()
            )
            embed.add_field(name="Level", value=player.level)
            embed.add_field(name="Health", value=f"{player.health}/{player.max_health}")
            embed.add_field(name="Mana", value=f"{player.mana}/{player.max_mana}")
            embed.add_field(name="XP", value=f"{player.xp}/{player.xp_needed_for_next_level()}")
            await ctx.send(embed=embed)
        else:
            await ctx.send("You haven't started your adventure yet! Use `!w start` to begin!")

async def setup(bot):
    await bot.add_cog(PlayerCommands(bot))