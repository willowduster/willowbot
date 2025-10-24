import asyncio
import aiosqlite

async def init_db():
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
                current_enemy TEXT DEFAULT NULL,
                inventory TEXT DEFAULT NULL,
                equipment TEXT DEFAULT NULL
            )
        ''')
        await db.commit()
        print("Database initialized successfully!")

if __name__ == '__main__':
    asyncio.run(init_db())