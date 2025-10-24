# WillowBot

A Discord RPG bot that allows users to create and manage characters with stats, levels, and more!

## Features

- Character creation and management
- Stats system including:
  - Health and Mana
  - Experience (XP) and Leveling
  - Automatic level-up system with stat increases

## Commands

- `!wb start` - Create your character and begin your adventure
- `!wb stats` - View your character's current stats

## Setup

1. Clone this repository
2. Create a `.env` file based on `example.env` with your:
   - Discord bot token (`DISCORD_TOKEN`)
   - Admin user ID (`ADMIN_USER_ID`)
3. Install dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
4. Run the bot:
   ```bash
   python src/bot.py
   ```

## Requirements

- Python 3.12+
- discord.py
- python-dotenv
- aiosqlite

## Database

The bot uses SQLite for data storage. The database file (`players.db`) will be created automatically when the bot starts.

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
│   │   └── player.py    # Player-related commands
│   └── models/          # Data models
│       └── player.py    # Player class definition
├── .env                 # Configuration (not in repo)
├── example.env          # Example configuration
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to your branch
5. Open a Pull Request