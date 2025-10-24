#!/usr/bin/env python3
"""
Clear all active quests from the database.
This is useful when quest IDs have changed in the config.
"""
import sqlite3
import os

# Path to the database (inside Docker volume)
DB_PATH = 'data/willowbot.db'

def clear_active_quests():
    """Remove all active quests from the database"""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        print("Make sure you're running this from the willowbot directory")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get count of active quests
    cursor.execute('SELECT COUNT(*) FROM active_quests')
    count = cursor.fetchone()[0]
    
    if count == 0:
        print("No active quests found in database")
        conn.close()
        return
    
    print(f"Found {count} active quest(s)")
    
    # Delete all active quests
    cursor.execute('DELETE FROM active_quests')
    conn.commit()
    
    print(f"✅ Cleared {count} active quest(s) from database")
    print("Players can now start fresh quests with the new quest IDs")
    
    conn.close()

if __name__ == '__main__':
    print("Quest Database Cleanup Tool")
    print("=" * 40)
    clear_active_quests()
