import discord
from discord.ext import commands
from models.player import Player
import aiosqlite
import os

class PlayerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_path = 'players.db'
        self.bot.loop.create_task(self.setup_database())
    
    async def setup_database(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    level INTEGER,
                    xp INTEGER,
                    health INTEGER,
                    max_health INTEGER,
                    mana INTEGER,
                    max_mana INTEGER
                )
            ''')
            await db.commit()
    
    async def get_player(self, user_id: int) -> Player:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT * FROM players WHERE id = ?', (user_id,)) as cursor:
                if row := await cursor.fetchone():
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

    @commands.command(name='stats')
    async def stats(self, ctx):
        """View your character stats"""
        if player := await self.get_player(ctx.author.id):
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
            await ctx.send("You haven't started your adventure yet! Use `!wb start` to begin!")

async def setup(bot):
    await bot.add_cog(PlayerCommands(bot))