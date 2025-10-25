import os
import asyncio
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import sqlite3
from threading import Thread
import sys
import yaml
from dotenv import load_dotenv
import requests
from functools import wraps

# Load environment variables from .env file
load_dotenv()

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.bot import WillowBot

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24))  # For session management

# Discord OAuth2 Configuration
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:5000/callback')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')

# Debug logging for environment variables (Railway troubleshooting)
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info(f"DISCORD_CLIENT_ID is {'SET' if DISCORD_CLIENT_ID else 'NOT SET'}")
logger.info(f"DISCORD_CLIENT_SECRET is {'SET' if DISCORD_CLIENT_SECRET else 'NOT SET'}")
logger.info(f"ADMIN_USER_ID is {'SET' if ADMIN_USER_ID else 'NOT SET'}")
logger.info(f"DISCORD_REDIRECT_URI: {DISCORD_REDIRECT_URI}")

# Discord API endpoints
DISCORD_API_BASE = 'https://discord.com/api/v10'
DISCORD_AUTHORIZATION_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = f'{DISCORD_API_BASE}/oauth2/token'
DISCORD_USER_URL = f'{DISCORD_API_BASE}/users/@me'

bot_instance = None
bot_thread = None

# Load items data
def load_items():
    items_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'config', 'items.yaml')
    try:
        with open(items_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data.get('items', {})
    except FileNotFoundError:
        return {}

# Load quests data
def load_quests():
    quests_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'config', 'quests.yaml')
    try:
        with open(quests_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            # Flatten quest chains into a dict with quest_id as key
            quests_dict = {}
            for chain in data.get('quest_chains', []):
                for quest in chain.get('quests', []):
                    quests_dict[quest['id']] = quest
            return quests_dict
    except FileNotFoundError:
        return {}

ITEMS_DATA = load_items()
QUESTS_DATA = load_quests()

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'discord_user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'discord_user' not in session:
            return redirect(url_for('login'))
        if session.get('discord_user', {}).get('id') != ADMIN_USER_ID:
            # Redirect non-admin users to their player page
            user_id = session.get('discord_user', {}).get('id')
            return redirect(url_for('get_player_details', player_id=user_id))
        return f(*args, **kwargs)
    return decorated_function

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

# ==================== Authentication Routes ====================

@app.route('/login')
def login():
    """Redirect to Discord OAuth2 login"""
    if not DISCORD_CLIENT_ID:
        return "Discord OAuth2 not configured. Please set DISCORD_CLIENT_ID in .env", 500
    
    params = {
        'client_id': DISCORD_CLIENT_ID,
        'redirect_uri': DISCORD_REDIRECT_URI,
        'response_type': 'code',
        'scope': 'identify'
    }
    auth_url = f"{DISCORD_AUTHORIZATION_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    """Handle Discord OAuth2 callback"""
    code = request.args.get('code')
    if not code:
        return "Authorization failed", 400
    
    # Exchange code for access token
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    token_response = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers)
    if token_response.status_code != 200:
        return f"Failed to get access token: {token_response.text}", 400
    
    token_data = token_response.json()
    access_token = token_data.get('access_token')
    
    # Get user info
    headers = {'Authorization': f'Bearer {access_token}'}
    user_response = requests.get(DISCORD_USER_URL, headers=headers)
    if user_response.status_code != 200:
        return "Failed to get user info", 400
    
    user_data = user_response.json()
    
    # Store user in session
    session['discord_user'] = {
        'id': user_data.get('id'),
        'username': user_data.get('username'),
        'discriminator': user_data.get('discriminator'),
        'avatar': user_data.get('avatar')
    }
    session['is_admin'] = (user_data.get('id') == ADMIN_USER_ID)
    
    # Redirect based on admin status
    if session['is_admin']:
        return redirect(url_for('index'))
    else:
        # Redirect to user's player page
        return redirect(url_for('get_player_details', player_id=user_data.get('id')))

@app.route('/logout')
def logout():
    """Log out the current user"""
    session.clear()
    return redirect(url_for('login'))

# ==================== Protected Routes ====================

@app.route('/')
@admin_required
def index():
    return render_template('index.html', user=session.get('discord_user'))

@app.route('/api/bot/status')
def bot_status():
    global bot_instance
    return jsonify({
        'running': bot_instance is not None and bot_instance.is_ready()
    })

@app.route('/api/bot/start', methods=['POST'])
@admin_required
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
@admin_required
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
@admin_required
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
@login_required
def get_player_details(player_id):
    # Check if user is admin or viewing their own page
    current_user_id = session.get('discord_user', {}).get('id')
    is_admin = session.get('is_admin', False)
    
    if not is_admin and str(player_id) != current_user_id:
        return "Access denied: You can only view your own player page", 403
    
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
    
    deaths = db.execute('''
        SELECT enemy_name, enemy_level, player_level, 
               player_health, player_max_health, player_mana, player_max_mana, died_at
        FROM death_history
        WHERE player_id = ?
        ORDER BY died_at DESC
    ''', [player_id]).fetchall()
    
    # Enrich inventory with item details
    inventory_with_details = []
    for inv_item in inventory:
        item_data = ITEMS_DATA.get(inv_item['item_id'], {})
        inventory_with_details.append({
            'item_id': inv_item['item_id'],
            'count': inv_item['count'],
            'name': item_data.get('name', inv_item['item_id']),
            'type': item_data.get('type', 'unknown'),
            'rarity': item_data.get('rarity', 'common'),
            'effects': item_data.get('effects', [])
        })
    
    # Enrich quests with quest details
    quests_with_details = []
    for quest_row in quests:
        quest_data = QUESTS_DATA.get(quest_row['quest_id'], {})
        quests_with_details.append({
            'quest_id': quest_row['quest_id'],
            'quest_name': quest_data.get('title', quest_row['quest_id']),
            'description': quest_data.get('description', ''),
            'objectives_progress': quest_row['objectives_progress'],
            'completed': quest_row['completed'],
            'rewards_claimed': quest_row['rewards_claimed']
        })
    
    return render_template(
        'player_details.html',
        player=player,
        inventory=inventory_with_details,
        quests=quests_with_details,
        kills=kills,
        total_kills=total_kills['total'] if total_kills else 0,
        deaths=deaths,
        user=session.get('discord_user'),
        is_admin=session.get('is_admin', False)
    )

@app.route('/api/items')
@admin_required
def get_items():
    # Load items from YAML config
    items_list = []
    for item_id, item_data in ITEMS_DATA.items():
        items_list.append({
            'id': item_id,
            'name': item_data.get('name', item_id),
            'type': item_data.get('type', 'unknown'),
            'rarity': item_data.get('rarity', 'common'),
            'level_requirement': item_data.get('level_requirement', 1),
            'value': item_data.get('value', 0),
            'description': item_data.get('description', ''),
            'effects': item_data.get('effects', [])
        })
    
    # Sort by rarity (legendary > rare > uncommon > common) then by level
    rarity_order = {'legendary': 0, 'rare': 1, 'uncommon': 2, 'common': 3}
    items_list.sort(key=lambda x: (rarity_order.get(x['rarity'], 4), x['level_requirement']))
    
    return render_template('items.html', items=items_list)

@app.route('/api/quests')
@admin_required
def get_quests():
    # Load quests from YAML config
    quests_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'config', 'quests.yaml')
    
    try:
        with open(quests_path, 'r', encoding='utf-8') as f:
            quests_data = yaml.safe_load(f)
    except FileNotFoundError as e:
        quests_data = {}
    except Exception as e:
        quests_data = {}
    
    # Load items for name lookups
    items_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'config', 'items.yaml')
    try:
        with open(items_path, 'r', encoding='utf-8') as f:
            items_data = yaml.safe_load(f)
            items_dict = items_data.get('items', {})
    except:
        items_dict = {}
    
    # Get active quest stats from database
    db = get_db()
    quest_stats = {}
    stats_rows = db.execute('''
        SELECT quest_id,
               SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) as active_players,
               SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed_players
        FROM active_quests
        GROUP BY quest_id
    ''').fetchall()
    
    for row in stats_rows:
        quest_stats[row[0]] = {
            'active_players': row[1] or 0,
            'completed_players': row[2] or 0
        }
    
    # Extract quests from quest_chains structure
    quests_list = []
    quest_chains = quests_data.get('quest_chains', [])
    
    # Build a mapping of quest IDs to titles for next_quest lookups
    quest_id_to_title = {}
    for chain in quest_chains:
        for quest in chain.get('quests', []):
            quest_id_to_title[quest.get('id', '')] = quest.get('title', '')
    
    for chain in quest_chains:
        for quest in chain.get('quests', []):
            quest_id = quest.get('id', '')
            stats = quest_stats.get(quest_id, {'active_players': 0, 'completed_players': 0})
            next_quest_id = quest.get('next_quest', '')
            
            # Enrich item rewards with names
            rewards = quest.get('rewards', {})
            if 'items' in rewards:
                enriched_items = []
                for item in rewards['items']:
                    item_id = item.get('id', '')
                    item_data = items_dict.get(item_id, {})
                    enriched_items.append({
                        'id': item_id,
                        'name': item_data.get('name', item_id),
                        'count': item.get('count', 1)
                    })
                rewards = dict(rewards)  # Make a copy
                rewards['items'] = enriched_items
            
            quests_list.append({
                'id': quest_id,
                'title': quest.get('title', ''),
                'description': quest.get('description', ''),
                'type': quest.get('type', ''),
                'objectives': quest.get('objectives', []),
                'rewards': rewards,
                'requirements': quest.get('requirements', {}),
                'next_quest': quest.get('next_quest', ''),
                'next_quest_title': quest_id_to_title.get(next_quest_id, next_quest_id) if next_quest_id else '',
                'active_players': stats['active_players'],
                'completed_players': stats['completed_players']
            })
    
    return render_template('quests.html', quests=quests_list)

@app.route('/api/players/reset', methods=['POST'])
@admin_required
def reset_all_players():
    try:
        db = get_db()
        
        # Delete all player-related data
        db.execute('DELETE FROM death_history')
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