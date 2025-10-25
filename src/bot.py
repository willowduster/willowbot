import os
import discord
import logging
import aiosqlite
from discord.ext import commands
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('willowbot')

class WillowBot(commands.Bot):
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Setup with intents
        intents = discord.Intents.all()
        
        # Define required permissions
        self.required_permissions = discord.Permissions(
            send_messages=True,
            read_messages=True,
            manage_messages=True,  # For editing/deleting messages
            add_reactions=True,    # For quest and combat reactions
            read_message_history=True,
            embed_links=True,      # For sending embeds
            attach_files=True,     # For potential future features
            external_emojis=True,  # For custom emojis if needed
            create_public_threads=True,  # For creating combat threads
            send_messages_in_threads=True,  # For posting in combat threads
            manage_threads=True    # For archiving threads after combat
        )
        
        super().__init__(command_prefix='!w ', intents=intents)
        
        # Set database path to Docker volume
        self.db_path = os.environ.get('DATABASE_PATH', '/app/data/willowbot.db')
        
        # Initialize extensions
        self.initial_extensions = [
            'src.commands.player',
            'src.commands.quests',
            'src.commands.combat',
            'src.commands.inventory'
        ]
    
    async def get_invite_link(self):
        """Generate an invite link with the required permissions"""
        app_info = await self.application_info()
        return discord.utils.oauth_url(
            app_info.id,
            permissions=self.required_permissions
        )
            
    async def check_channel_permissions(self, channel):
        """Check if the bot has the required permissions in a channel"""
        bot_member = channel.guild.me
        channel_perms = channel.permissions_for(bot_member)
        
        missing_perms = []
        for perm_name, required in self.required_permissions:
            if required and not getattr(channel_perms, perm_name):
                missing_perms.append(perm_name)
                
        return missing_perms
        
    async def ensure_permissions(self, channel):
        """Ensure the bot has all required permissions, send warning if not"""
        missing_perms = await self.check_channel_permissions(channel)
        if missing_perms:
            try:
                invite_link = await self.get_invite_link()
                warning = (
                    f"⚠️ Missing required permissions: {', '.join(missing_perms)}\n"
                    f"Please ensure the bot has the correct permissions or reinvite using: {invite_link}"
                )
                await channel.send(warning)
                return False
            except discord.Forbidden:
                # Can't even send the warning message
                logger.warning(f"Missing critical permissions in channel {channel.id}")
                return False
        return True
    
    async def db_connect(self):
        """Create a new database connection as an async context manager"""
        return aiosqlite.connect(self.db_path)

    async def setup_hook(self):
        logger.info("Starting bot setup")
        # Set environment
        os.environ['DATABASE_PATH'] = self.db_path
        logger.info(f"Database path set to: {self.db_path}")
        
        # Setup core database schema
        from setup import setup_database, create_items_config
        from src.models.quest_manager import QuestManager
        from src.models.inventory_manager import InventoryManager
        
        logger.info("Setting up database schema")
        
        await setup_database()  # Core schema
        
        # Initialize schemas for each component
        async with await self.db_connect() as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    level INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    health INTEGER DEFAULT 100,
                    max_health INTEGER DEFAULT 100,
                    mana INTEGER DEFAULT 100,
                    max_mana INTEGER DEFAULT 100,
                    damage_bonus INTEGER DEFAULT 0,
                    magic_damage_bonus INTEGER DEFAULT 0,
                    defense INTEGER DEFAULT 0,
                    magic_defense INTEGER DEFAULT 0,
                    crit_chance_bonus REAL DEFAULT 0.0,
                    flee_chance_bonus REAL DEFAULT 0.0,
                    health_bonus INTEGER DEFAULT 0,
                    mana_bonus INTEGER DEFAULT 0,
                    gold INTEGER DEFAULT 0,
                    current_title TEXT DEFAULT NULL,
                    in_combat BOOLEAN DEFAULT FALSE,
                    current_enemy TEXT DEFAULT NULL,
                    deaths INTEGER DEFAULT 0
                )
            ''')
            
            # Migration: Add gold column if it doesn't exist
            try:
                await db.execute('SELECT gold FROM players LIMIT 1')
            except:
                logger.info("Adding gold column to players table")
                await db.execute('ALTER TABLE players ADD COLUMN gold INTEGER DEFAULT 0')
                await db.commit()
            
            # Migration: Add deaths column if it doesn't exist
            try:
                await db.execute('SELECT deaths FROM players LIMIT 1')
            except:
                logger.info("Adding deaths column to players table")
                await db.execute('ALTER TABLE players ADD COLUMN deaths INTEGER DEFAULT 0')
                await db.commit()

            # Active quests table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS active_quests (
                    player_id INTEGER,
                    quest_id TEXT,
                    completed BOOLEAN DEFAULT FALSE,
                    rewards_claimed BOOLEAN DEFAULT FALSE,
                    objectives_progress TEXT,  -- JSON string of objective progress
                    FOREIGN KEY(player_id) REFERENCES players(id),
                    PRIMARY KEY (player_id, quest_id)
                )
            ''')

            # Player kills tracking table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_kills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER,
                    enemy_name TEXT NOT NULL,
                    enemy_level INTEGER NOT NULL,
                    killed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(player_id) REFERENCES players(id)
                )
            ''')
            
            # Player death history table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS death_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_id INTEGER,
                    enemy_name TEXT NOT NULL,
                    enemy_level INTEGER NOT NULL,
                    player_level INTEGER NOT NULL,
                    player_health INTEGER NOT NULL,
                    player_max_health INTEGER NOT NULL,
                    player_mana INTEGER NOT NULL,
                    player_max_mana INTEGER NOT NULL,
                    died_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(player_id) REFERENCES players(id)
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

            await db.commit()
        
        # Load items configuration
        create_items_config()
        
        # Load extensions
        for extension in self.initial_extensions:
            await self.load_extension(extension)

    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        print('Bot is ready to play!')

    def is_ready(self):
        return self.is_closed() is False
        
    async def close(self):
        await super().close()

# Run bot when executed directly
if __name__ == '__main__':
    bot = WillowBot()
    bot.run(os.getenv('DISCORD_TOKEN'))