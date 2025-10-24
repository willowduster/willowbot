# WillowBot

A Discord RPG bot that allows users to create and manage characters with stats, levels, and more!

## Features

- Character creation and management
- Stats system including:
  - Health and Mana
  - Experience (XP) and Leveling
  - Automatic level-up system with stat increases
- Equipment and Inventory
  - Various item types (weapons, armor, consumables)
  - Item rarity system
  - Equipment slots with stat bonuses
- Combat System
  - Turn-based combat with enemies
  - Melee and magic attacks
  - Critical hits and miss chances
  - Enemy affixes and special abilities
- Quest System
  - Multiple quest chains
  - Various objective types
  - Rewards including items, XP, gold, and titles

## Commands

Character Management:
- `!wb start` - Create your character and begin your adventure
- `!wb stats` - View your character's current stats

Equipment & Inventory:
- `!wb inventory` - View your inventory
- `!wb equip <item>` - Equip an item
- `!wb unequip <slot>` - Unequip an item from a slot

Combat:
- `!wb attack <type>` - Use a melee or magic attack
- `!wb flee` - Attempt to flee from combat

Quests:
- `!wb quests` - List available quests
- `!wb start_quest <quest_id>` - Start a specific quest
- `!wb quest_progress` - Check your current quest progress
- `!wb claim_rewards <quest_id>` - Claim rewards for a completed quest

## Setup

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

## Requirements

- Python 3.12+
- discord.py
- python-dotenv
- aiosqlite

## Database

The bot uses SQLite for data storage. The database file (`players.db`) will be created automatically when the bot starts. The database schema includes:

- Player data (stats, level, XP)
- Inventory system
- Equipment loadouts
- Active quests and progress
- Quest completion records
- Combat state tracking

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
├── .env                 # Configuration (not in repo)
├── example.env          # Example configuration
├── requirements.txt     # Python dependencies
├── setup.py            # Database initialization script
└── README.md           # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your branch
5. Open a Pull Request