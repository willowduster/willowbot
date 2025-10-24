import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot setup with intents
intents = discord.Intents.all()  # Enable all intents since we need message content and members

bot = commands.Bot(command_prefix='!wb ', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print('Bot is ready to play!')

# Load command extensions
initial_extensions = [
    'commands.player',
    'commands.combat',
    'commands.quests',
    'commands.inventory',
]

async def load_extensions():
    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)
        except Exception as e:
            print(f'Failed to load extension {extension}. Error: {e}')

async def main():
    async with bot:
        await load_extensions()
        await bot.start(os.getenv('DISCORD_TOKEN'))

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())