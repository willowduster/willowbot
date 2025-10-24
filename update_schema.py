import sqlite3
import asyncio
import aiosqlite

async def update_schema():
    async with aiosqlite.connect('willowbot.db') as db:
        await db.execute('BEGIN TRANSACTION')
        
        # Create a backup of the players table
        await db.execute('CREATE TABLE players_backup AS SELECT * FROM players')
        
        # Drop the existing table
        await db.execute('DROP TABLE players')
        
        # Recreate the table with all columns
        await db.execute('''
            CREATE TABLE players (
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
        
        # Copy data back from backup
        await db.execute('''
            INSERT INTO players 
            SELECT 
                id, name, level, xp, health, max_health, mana, max_mana,
                0, 0, 0, 0, 0.0, 0.0, 0, 0,
                in_combat, current_enemy,
                inventory,
                NULL as equipment
            FROM players_backup
        ''')
        
        # Drop the backup table
        await db.execute('DROP TABLE players_backup')
        
        await db.execute('COMMIT')

if __name__ == '__main__':
    asyncio.run(update_schema())