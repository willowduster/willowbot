import os
import asyncio
from flask import Flask, render_template, jsonify, request
import sqlite3
from threading import Thread
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.bot import WillowBot

app = Flask(__name__)
bot_instance = None
bot_thread = None

def start_bot_if_not_running():
    global bot_instance, bot_thread
    if bot_instance is None or not bot_instance.is_ready():
        bot_instance = WillowBot()
        token = os.getenv('DISCORD_TOKEN')
        if token:
            bot_thread = Thread(target=lambda: bot_instance.run(token))
            bot_thread.start()

def get_db():
    db_path = os.environ.get('DATABASE_PATH', '/app/data/willowbot.db')
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    return db

# Start bot when Flask starts
with app.app_context():
    start_bot_if_not_running()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/bot/status')
def bot_status():
    global bot_instance
    return jsonify({
        'running': bot_instance is not None and bot_instance.is_ready()
    })

@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    global bot_instance, bot_thread
    if bot_instance is None or not bot_instance.is_ready():
        bot_instance = WillowBot()
        token = os.getenv('DISCORD_TOKEN')
        if not token:
            return jsonify({'status': 'error', 'message': 'Discord token not found in environment variables'})
        bot_thread = Thread(target=lambda: bot_instance.run(token))
        bot_thread.start()
        return jsonify({'status': 'started'})
    return jsonify({'status': 'already_running'})

@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    global bot_instance, bot_thread
    if bot_instance and bot_instance.is_ready():
        asyncio.run_coroutine_threadsafe(bot_instance.close(), bot_instance.loop)
        bot_thread.join()
        bot_instance = None
        bot_thread = None
        return jsonify({'status': 'stopped'})
    return jsonify({'status': 'not_running'})

@app.route('/api/players')
def get_players():
    db = get_db()
    players = db.execute('''
        SELECT p.*, 
               COUNT(DISTINCT aq.quest_id) as active_quests,
               COUNT(DISTINCT cq.quest_id) as completed_quests
        FROM players p
        LEFT JOIN active_quests aq ON p.id = aq.player_id
        LEFT JOIN active_quests cq ON p.id = cq.player_id AND cq.completed = 1
        GROUP BY p.id
    ''').fetchall()
    return render_template('players.html', players=players)

@app.route('/api/player/<int:player_id>')
def get_player_details(player_id):
    db = get_db()
    player = db.execute('SELECT * FROM players WHERE id = ?', [player_id]).fetchone()
    
    inventory = db.execute('''
        SELECT item_id, count
        FROM inventory
        WHERE player_id = ? AND count > 0
    ''', [player_id]).fetchall()
    
    quests = db.execute('''
        SELECT quest_id, objectives_progress, completed, rewards_claimed
        FROM active_quests
        WHERE player_id = ?
    ''', [player_id]).fetchall()
    
    kills = db.execute('''
        SELECT enemy_name, enemy_level, killed_at, COUNT(*) as count
        FROM player_kills
        WHERE player_id = ?
        GROUP BY enemy_name, enemy_level
        ORDER BY killed_at DESC
    ''', [player_id]).fetchall()
    
    total_kills = db.execute('''
        SELECT COUNT(*) as total FROM player_kills WHERE player_id = ?
    ''', [player_id]).fetchone()
    
    return render_template(
        'player_details.html',
        player=player,
        inventory=inventory,
        quests=quests,
        kills=kills,
        total_kills=total_kills['total'] if total_kills else 0
    )

@app.route('/api/items')
def get_items():
    # Items are stored in YAML config, not database
    # For now, return empty list or load from config if needed
    return render_template('items.html', items=[])

@app.route('/api/quests')
def get_quests():
    db = get_db()
    # Quests are stored in YAML config, just show active quest stats
    quests = db.execute('''
        SELECT quest_id,
               COUNT(*) as total_players,
               SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) as active_players,
               SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_players
        FROM active_quests
        GROUP BY quest_id
    ''').fetchall()
    return render_template('quests.html', quests=quests)

@app.route('/api/players/reset', methods=['POST'])
def reset_all_players():
    try:
        db = get_db()
        
        # Delete all player-related data
        db.execute('DELETE FROM player_kills')
        db.execute('DELETE FROM active_quests')
        db.execute('DELETE FROM inventory')
        db.execute('DELETE FROM equipment')
        db.execute('DELETE FROM players')
        
        db.commit()
        db.close()
        
        return jsonify({'status': 'success', 'message': 'All players have been reset'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)