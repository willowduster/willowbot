# WillowBot

A Discord RPG bot that allows users to create and manage characters with stats, levels, and more!

## Features

- **Character Creation and Management**
  - Create unique characters with custom stats
  - Track death and kill statistics
  - Death history with timestamps and causes
  - 10% gold/XP penalty on death

- **Stats System**
  - Health and Mana with regeneration
  - **Cumulative XP system** - XP carries over when leveling up
  - Automatic level-up system with stat increases
  - Comprehensive stat tracking (deaths, kills, quests completed)

- **Equipment and Inventory**
  - **100 unique items** across multiple categories
  - Various item types (weapons, armor, consumables, materials)
  - Item rarity system (Common, Uncommon, Rare, Epic, Legendary)
  - Equipment slots with stat bonuses
  - Use consumables for healing and buffs

- **Combat System**
  - Turn-based combat with enemies
  - Melee and magic attacks with emoji reactions
  - **Prayer system** - Restore mana when no potions available (20-40% mana restore)
  - Critical hits and miss chances
  - **150+ unique enemy combinations** with affixes
  - **30 enemy types** with prefix/suffix modifiers
  - Balanced difficulty with adjustable stats
  - **Flee mechanics** with action buttons after successful escape
  - Defeat system with heal/restart or leave options
  - Victory screen with rest option to restore HP/Mana
  - **Interactive combat log** with all actions and results
  - Death tracking and penalties

- **Quest System**
  - **50 quests** organized into **10 quest chains**
  - All combat-focused quests for streamlined gameplay
  - Progressive difficulty scaling
  - Rewards including items, XP, gold, and titles
  - Automatic quest chain progression
  - Quest completion tracking (quests marked as completed, not deleted)
  - Automatic reward claiming on completion
  - Auto-start combat when clicking "Next Quest" button

- **Web Dashboard**
  - Dark mode interface with GitHub-inspired theme
  - Real-time bot status monitoring
  - Player statistics and leaderboards
  - Complete item catalog (100 items) with filtering
  - Quest database (50 quests) with details
  - Death history viewer

## Commands

**Getting Help:**
- `!w help` or `!w h` - Interactive help menu with quick action buttons
  - ▶️ Start Adventure (for new players)
  - 🎯 Continue Playing (shows quests for existing players)
  - ❌ Close menu
  - All commands, combat actions, and tips on one page

**Character Management:**
- `!w start` - Create your character and begin your adventure
- `!w stats` or `!w s` - View your character's current stats including deaths and kills

**Equipment & Inventory:**
- `!w inventory` - View your inventory
- `!w equip <item>` - Equip an item
- `!w unequip <slot>` - Unequip an item from a slot
- `!w use <item>` - Use a consumable item

**Combat:**
- `⚔️` - Use a melee attack (reaction emoji)
- `🔮` - Use a magic attack (reaction emoji)
- `🧪` - Use a potion during combat (reaction emoji)
- `🏃` - Attempt to flee from combat (reaction emoji)
- `🙏` - Pray to restore mana (20-40% mana restore when no potions available)
- Interactive defeat system with options to heal or leave
- `🛏️` - Rest to restore HP and Mana after victory or successful flee (reaction emoji)
- `▶️` - Continue to next quest or enemy (reaction emoji)
- `🔄` - Retry quest after fleeing or resting (reaction emoji)
- `🎒` - View inventory after combat (reaction emoji)
- `📊` - View stats after combat (reaction emoji)

**Quests:**
- `!w quests` or `!w q` - List available quests
- `!w start_quest <quest_id>` - Start a specific quest
- `!w quest_progress` - Check your current quest progress
- Automatic quest chain progression
- Automatic reward claiming on completion

## Setup

### Standard Setup

1. Clone this repository
2. Create a `.env` file based on `example.env` with your:
   - Discord bot token (`DISCORD_TOKEN`)
   - Admin user ID (`ADMIN_USER_ID`)
3. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
4. Initialize the database:
   ```bash
   python setup.py
   ```
   This will create the database schema and load items from `src/config/items.yaml`.
5. Run the bot:
   ```bash
   python src/bot.py
   ```

### Docker Setup

1. Clone this repository
2. Create a `.env` file as described above
3. Build and start the containers:
   ```bash
   docker-compose up -d
   ```
   This will:
   - Build the Docker image
   - Initialize the database
   - Start the bot and web interface
   - Mount the database file in the `data` directory
4. Access the web interface at http://localhost:5000

## Web Interface

The web interface provides a modern dark mode dashboard to monitor and manage your bot:

**Features:**
- **Dashboard** (`/`) - Bot control panel with start/stop functionality and quick stats
- **Players** (`/api/players`) - Complete player list with detailed stats including:
  - Level, XP, HP, Mana
  - Gold and inventory items
  - Death and kill statistics
  - Active quests with quest names and IDs
  - Quest completion records
  - Detailed death history with timestamps
- **Items** (`/api/items`) - Comprehensive item catalog with:
  - Rarity-based color coding
  - Detailed stats and effects
  - Item type filtering
  - Dark mode card layout
- **Quests** (`/api/quests`) - Quest database showing:
  - All available quest chains
  - Quest objectives and rewards
  - Player participation statistics
  - Active and completed quest counts

**Design:**
- GitHub-inspired dark theme
- Bootstrap 5.3.0 with native dark mode
- Responsive card-based layout
- Unified navigation across all pages
- Color-coded rarity system for items

The interface runs on **port 5000** by default. Access it at `http://localhost:5000` after starting the bot.

## Requirements

- Python 3.12+
- discord.py
- python-dotenv
- aiosqlite

## Database

The bot uses SQLite for data storage. The database file (`willowbot.db`) will be created automatically when the bot starts. The database schema includes:

- **Players table** - Character data (stats, level, XP, deaths, kills)
- **Inventory table** - Player item storage
- **Equipment table** - Equipped items per player
- **Active quests table** - Current quest progress
- **Completed quests table** - Quest completion history
- **Combat state table** - Active combat tracking
- **Death history table** - Timestamped death records with causes

All data persists in the `data/` directory and survives container restarts.

## Configuration

The bot includes extensive YAML-based configuration files:

### Items Configuration (`src/config/items.yaml`)
- **100 unique items** across categories:
  - 20 Weapons (swords, axes, bows, staves)
  - 12 Helmets
  - 15 Armor pieces
  - 10 Pants
  - 10 Boots
  - 10 Rings
  - 10 Amulets
  - 13 Consumables (health/mana potions, buffs)
  - 10 Materials
- Item effects: damage bonuses, health/mana boosts, defense, resistances
- Rarity levels: Common, Uncommon, Rare, Epic, Legendary

### Quest Configuration (`src/config/quests.yaml`)
- **50 quests** organized into **10 quest chains**
- All combat-type quests for consistent gameplay experience
- Progressive difficulty scaling
- Rewards: XP, gold, items from items.yaml
- Quest chains with sequential progression

### Enemy Configuration (`src/config/enemies.yaml`)
- **30 base enemy types**: Beasts, Undead, Elementals, Dragons, Demons, Insects, Reptiles, Goblinoids, Constructs, Aquatic, Avian, Plants, Aberrations, Fey, Celestial, Infernal, Shadow, Ooze, Swarm, Humanoid, Giant, Shapeshifter, Parasites, Fungus, Underdark, Ethereal, Primordial, Mechanical, Corrupted, Eldritch
- **10 prefixes**: Fierce, Tough, Magical, Swift, Ancient, Savage, Armored, Berserker, Cunning, Massive
- **10 suffixes**: of Darkness, of the Mountain, of Rage, of Wisdom, of Speed, of Power, of Protection, of Destruction, of the Void, of Eternity
- **150+ unique combinations** possible
- Balanced stats for fair combat
- Attack types: melee and magic with varying damage, mana costs, miss/crit chances

### Utility Scripts
- `expand_configs.py` - Generate large-scale configurations
- `balance_enemies.py` - Adjust enemy difficulty (HP, damage, miss/crit rates, affixes)
- `clear_quests.py` - Clean up old quest data from database

## Invite Link

To add the bot to your server, you'll need:
1. Create a Discord application at https://discord.com/developers/applications
2. Enable all privileged intents (Presence, Server Members, Message Content)
3. Generate an invite link with the following permissions:
   - Read Messages/View Channels
   - Send Messages
   - Embed Links
   - Read Message History

## Development

The project structure is organized as follows:
```
willowbot/
├── src/
│   ├── bot.py           # Main bot file
│   ├── commands/        # Bot commands
│   │   ├── player.py    # Player-related commands
│   │   ├── combat.py    # Combat-related commands
│   │   └── quests.py    # Quest-related commands
│   ├── config/          # Configuration files
│   │   ├── items.yaml   # Items configuration
│   │   ├── quests.yaml  # Quest chains and rewards
│   │   └── enemies.yaml # Enemy types and abilities
│   └── models/          # Data models
│       ├── player.py    # Player class definition
│       ├── combat.py    # Combat mechanics
│       ├── enemy.py     # Enemy generation
│       ├── inventory.py # Inventory management
│       ├── equipment.py # Equipment management
│       └── quest.py     # Quest system
├── webservice/         # Web interface
│   ├── app.py          # Flask application
│   └── templates/      # HTML templates
│       ├── base.html       # Dark mode base template
│       ├── index.html      # Dashboard
│       ├── players.html    # Player list
│       ├── items.html      # Item catalog
│       └── quests.html     # Quest database
├── data/              # Persistent data directory
│   └── willowbot.db   # SQLite database
├── .env               # Configuration (not in repo)
├── example.env        # Example configuration
├── requirements.txt   # Python dependencies
├── setup.py          # Database initialization script
├── Dockerfile        # Docker configuration
├── docker-compose.yml # Docker Compose configuration
└── README.md         # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your branch
5. Open a Pull Request