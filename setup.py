import asyncio
import aiosqlite
import os
from pathlib import Path
import yaml

async def setup_database():
    async with aiosqlite.connect('willowbot.db') as db:
        # Create players table
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
                in_combat BOOLEAN DEFAULT FALSE,
                current_enemy TEXT DEFAULT NULL
            )
        ''')

        # Create inventory table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                player_id INTEGER,
                item_id TEXT,
                count INTEGER DEFAULT 1,
                FOREIGN KEY(player_id) REFERENCES players(id),
                PRIMARY KEY(player_id, item_id)
            )
        ''')

        # Create equipment table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS equipment (
                player_id INTEGER PRIMARY KEY,
                helmet_id TEXT DEFAULT NULL,
                armor_id TEXT DEFAULT NULL,
                pants_id TEXT DEFAULT NULL,
                boots_id TEXT DEFAULT NULL,
                weapon_id TEXT DEFAULT NULL,
                ring1_id TEXT DEFAULT NULL,
                ring2_id TEXT DEFAULT NULL,
                amulet_id TEXT DEFAULT NULL,
                FOREIGN KEY(player_id) REFERENCES players(id)
            )
        ''')

        await db.commit()
        print("Database schema created successfully!")

def create_items_config():
    """Load items configuration from items.yaml file"""
    config_path = Path('src/config')
    config_path.mkdir(parents=True, exist_ok=True)
    
    items_file = config_path / 'items.yaml'
    
    try:
        with open(items_file, 'r') as f:
            items = yaml.safe_load(f)
            if not items or 'items' not in items:
                raise ValueError("Invalid items.yaml format")
            print("Items configuration loaded successfully")
            return items
    except FileNotFoundError:
        print(f"Error: items.yaml not found at {items_file}")
        return None
    except Exception as e:
        print(f"Error loading items.yaml: {e}")
        return None

async def main():
    # Create database
    await setup_database()
    
    # Load items configuration
    items = create_items_config()
    if not items:
        print("Failed to load items configuration")
        return
    
    print(f"Loaded {len(items['items'])} items from configuration")

if __name__ == "__main__":
    asyncio.run(main())