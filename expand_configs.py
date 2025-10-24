#!/usr/bin/env python3
"""Script to expand configuration files to requested sizes"""

import yaml
import random

def expand_items_to_100():
    """Expand items configuration to 100 items"""
    
    # Base templates for different item types
    weapon_names = [
        ("Rusty Sword", "A basic sword showing signs of wear", 5),
        ("Steel Sword", "A well-crafted steel sword", 12),
        ("Iron Axe", "A heavy battle axe", 15),
        ("Flame Blade", "A magical sword imbued with fire", 20),
        ("Crystal Wand", "A wand made of pure crystal", 18),
        ("Shadow Dagger", "A dagger that strikes from the shadows", 22),
        ("Holy Mace", "A mace blessed with holy power", 25),
        ("Thunderbolt Spear", "A spear crackling with lightning", 40),
        ("Dragon Slayer", "Forged from dragon scales", 85),
        ("Wooden Bow", "A simple hunting bow", 8),
        ("Composite Bow", "A well-crafted composite bow", 20),
        ("Frost Hammer", "A massive hammer imbued with frost", 35),
        ("Poison Blade", "A blade coated with deadly poison", 18),
        ("War Scythe", "A deadly curved blade on a long pole", 32),
        ("Void Staff", "A staff channeling void power", 60),
        ("Arcane Blade", "A sword forged with arcane energy", 45),
        ("Soul Reaper", "A cursed weapon that drains life", 70),
        ("Celestial Bow", "A bow blessed by the stars", 65),
        ("Demon Claw", "Gauntlets with demonic claws", 55),
        ("Lightning Rod", "A staff that calls lightning", 50),
    ]
    
    items = {
        "items": {}
    }
    
    item_id = 0
    
    # Add 20 weapons
    for i, (name, desc, dmg) in enumerate(weapon_names):
        item_id = f"weapon_{i+1}"
        rarity = ["common", "uncommon", "rare", "epic", "legendary"][(i // 4) % 5]
        lvl = (i // 2) + 1
        
        items["items"][item_id] = {
            "id": item_id,
            "name": name,
            "description": desc,
            "type": "weapon",
            "rarity": rarity,
            "level_requirement": lvl,
            "value": dmg * 10,
            "stackable": False,
            "effects": [
                {"type": "damage", "value": dmg}
            ]
        }
        
        if i % 3 == 0:
            items["items"][item_id]["effects"].append({"type": "crit_chance", "value": 5 + (i // 2)})
    
    # Add helmets, armor, pants, boots (40 items)
    armor_types = ["helmet", "armor", "pants", "boots"]
    armor_names = {
        "helmet": ["Cap", "Helmet", "Hood", "Crown", "Helm", "Cowl", "Circlet", "Hat", "Mask", "Visor"],
        "armor": ["Robe", "Mail", "Plate", "Tunic", "Vest", "Cuirass", "Harness", "Suit", "Garb", "Vestments"],
        "pants": ["Pants", "Leggings", "Greaves", "Trousers", "Breeches", "Chaps", "Leg Guards", "Cuisses", "Leg Plates", "Sabatons"],
        "boots": ["Boots", "Shoes", "Sandals", "Greaves", "Sabatons", "Treads", "Footwear", "Slippers", "Walkers", "Striders"]
    }
    
    for armor_type in armor_types:
        for i in range(10):
            item_id = f"{armor_type}_{i+1}"
            prefix = ["Leather", "Iron", "Steel", "Mage's", "Dragon", "Shadow", "Crystal", "Void", "Holy", "Demon"][i]
            name = f"{prefix} {armor_names[armor_type][i]}"
            
            rarity = ["common", "uncommon", "rare", "epic", "legendary"][(i // 2) % 5]
            lvl = (i * 2) + 1
            defense = 5 + (i * 3)
            
            items["items"][item_id] = {
                "id": item_id,
                "name": name,
                "description": f"Quality {armor_type} protection",
                "type": armor_type,
                "rarity": rarity,
                "level_requirement": lvl,
                "value": defense * 10,
                "stackable": False,
                "effects": [
                    {"type": "defense", "value": defense}
                ]
            }
            
            if i % 2 == 0:
                items["items"][item_id]["effects"].append({"type": "magic_defense", "value": defense // 2})
    
    # Add rings and amulets (20 items)
    accessories = ["ring", "amulet"]
    for acc_type in accessories:
        for i in range(10):
            item_id = f"{acc_type}_{i+1}"
            prefix = ["Copper", "Silver", "Gold", "Platinum", "Diamond", "Ruby", "Sapphire", "Emerald", "Dragon", "Void"][i]
            name = f"{prefix} {acc_type.title()}"
            
            rarity = ["common", "uncommon", "rare", "epic", "legendary"][(i // 2) % 5]
            lvl = (i * 2) + 1
            
            effects = []
            if i % 3 == 0:
                effects.append({"type": "max_health", "value": 20 + (i * 10)})
            if i % 3 == 1:
                effects.append({"type": "magic_damage", "value": 5 + (i * 2)})
            if i % 3 == 2:
                effects.append({"type": "crit_chance", "value": 3 + i})
            
            items["items"][item_id] = {
                "id": item_id,
                "name": name,
                "description": f"A {rarity} {acc_type}",
                "type": acc_type,
                "rarity": rarity,
                "level_requirement": lvl,
                "value": 50 + (i * 50),
                "stackable": False,
                "effects": effects
            }
    
    # Add consumables (10 items)
    consumables = [
        ("Health Potion", "Restores 50 HP", "heal", 50),
        ("Mana Potion", "Restores 50 mana", "mana_restore", 50),
        ("Greater Health Potion", "Restores 150 HP", "heal", 150),
        ("Greater Mana Potion", "Restores 150 mana", "mana_restore", 150),
        ("Superior Health Potion", "Restores 300 HP", "heal", 300),
        ("Superior Mana Potion", "Restores 300 mana", "mana_restore", 300),
        ("Elixir of Strength", "Increases damage by 25%", "damage_buff", 25),
        ("Elixir of Wisdom", "Increases magic damage by 25%", "magic_damage_buff", 25),
        ("Phoenix Down", "Revives from defeat", "revive", 50),
        ("XP Boost Potion", "Doubles XP gain", "exp_buff", 100),
    ]
    
    for i, (name, desc, effect_type, value) in enumerate(consumables):
        item_id = f"consumable_{i+1}"
        rarity = ["common", "uncommon", "rare", "epic", "legendary"][(i // 2) % 5]
        
        items["items"][item_id] = {
            "id": item_id,
            "name": name,
            "description": desc,
            "type": "consumable",
            "rarity": rarity,
            "level_requirement": 1 + (i * 2),
            "value": 25 + (i * 50),
            "stackable": True,
            "max_stack": 20,
            "effects": [
                {"type": effect_type, "value": value}
            ]
        }
    
    # Add materials (10 items)
    materials = [
        ("Bone Dust", "Powdered bones from undead"),
        ("Elemental Essence", "Pure magical essence"),
        ("Ancient Wolf Pelt", "Magnificent pelt from an ancient wolf"),
        ("Dragon Scale", "A scale from a mighty dragon"),
        ("Shadow Shard", "Solidified shadow fragment"),
        ("Crystal Fragment", "Piece of magical crystal"),
        ("Void Essence", "Pure void realm essence"),
        ("Demon Horn", "Horn from a defeated demon"),
        ("Holy Relic", "Ancient blessed artifact"),
        ("Beast Fang", "Sharp fang from a wild beast"),
    ]
    
    for i, (name, desc) in enumerate(materials):
        item_id = f"material_{i+1}"
        rarity = ["common", "uncommon", "rare", "epic", "legendary"][(i // 2) % 5]
        
        items["items"][item_id] = {
            "id": item_id,
            "name": name,
            "description": desc,
            "type": "material",
            "rarity": rarity,
            "level_requirement": 1,
            "value": 20 + (i * 100),
            "stackable": True,
            "max_stack": 50,
            "effects": []
        }
    
    return items

def expand_quests_to_50():
    """Expand quests configuration to 50 quests"""
    
    quest_types = ["combat", "boss_combat", "collection", "exploration"]
    enemy_types = ["Beast", "Undead", "Elemental", "Dragon", "Demon"]
    
    quest_chains = {
        "quest_chains": []
    }
    
    # Create 10 quest chains with 5 quests each
    for chain_idx in range(10):
        chain_id = f"chain_{chain_idx+1}"
        chain_name = f"Quest Chain {chain_idx+1}"
        chain_desc = f"A series of {random.choice(['challenging', 'epic', 'legendary', 'mysterious'])} quests"
        
        quests = []
        for quest_idx in range(5):
            quest_id = f"quest_{chain_idx+1}_{quest_idx+1}"
            quest_num = chain_idx * 5 + quest_idx + 1
            
            quest = {
                "id": quest_id,
                "title": f"Quest {quest_num}: {random.choice(['The Beginning', 'Rising Threat', 'Dark Times', 'Final Confrontation', 'Victory'])}",
                "description": f"Complete objective {quest_idx+1} of chain {chain_idx+1}",
                "type": random.choice(quest_types),
                "requirements": {
                    "level": (quest_num // 2) + 1
                },
                "objectives": [
                    {
                        "type": "combat",
                        "count": random.randint(1, 3),
                        "description": f"Defeat {random.randint(1, 5)} {random.choice(enemy_types)} enemies"
                    }
                ],
                "rewards": {
                    "xp": 100 + (quest_num * 50),
                    "gold": 50 + (quest_num * 25)
                }
            }
            
            if quest_idx > 0:
                quest["requirements"]["previous_quest"] = f"quest_{chain_idx+1}_{quest_idx}"
            
            if quest_idx < 4:
                quest["next_quest"] = f"quest_{chain_idx+1}_{quest_idx+2}"
            
            # Add item rewards to some quests
            if quest_idx % 2 == 0:
                quest["rewards"]["items"] = [
                    {"id": f"consumable_{random.randint(1, 10)}", "count": random.randint(1, 3)}
                ]
            
            quests.append(quest)
        
        quest_chains["quest_chains"].append({
            "id": chain_id,
            "name": chain_name,
            "description": chain_desc,
            "quests": quests
        })
    
    return quest_chains

def expand_enemies_to_150():
    """Expand enemies configuration to 150+ enemy combinations"""
    
    enemies = {
        "enemy_types": [],
        "affixes": {
            "prefixes": [],
            "suffixes": []
        }
    }
    
    # 30 enemy types with 5 names each = 150 base enemies
    enemy_templates = [
        ("Beast", ["Wolf", "Bear", "Lion", "Tiger", "Boar"]),
        ("Undead", ["Skeleton", "Zombie", "Ghost", "Wraith", "Ghoul"]),
        ("Elemental", ["Fire Spirit", "Water Elemental", "Earth Golem", "Wind Wisp", "Lightning Spark"]),
        ("Dragon", ["Young Dragon", "Wyvern", "Drake", "Wyrm", "Dragon Lord"]),
        ("Demon", ["Imp", "Hellhound", "Demon Warrior", "Succubus", "Demon Lord"]),
        ("Insect", ["Giant Spider", "Scorpion", "Mantis", "Wasp", "Beetle"]),
        ("Reptile", ["Lizardman", "Basilisk", "Hydra", "Serpent", "Crocodile"]),
        ("Goblinoid", ["Goblin", "Hobgoblin", "Orc", "Troll", "Ogre"]),
        ("Construct", ["Golem", "Automaton", "Gargoyle", "Sentinel", "War Machine"]),
        ("Aquatic", ["Merfolk", "Sea Serpent", "Kraken Spawn", "Naga", "Leviathan"]),
        ("Avian", ["Giant Eagle", "Harpy", "Roc", "Phoenix", "Thunderbird"]),
        ("Plant", ["Treant", "Vine Horror", "Spore Beast", "Man-Eater", "Bloom Terror"]),
        ("Aberration", ["Beholder", "Mind Flayer", "Gibbering Mouther", "Otyugh", "Aboleth"]),
        ("Celestial", ["Angel", "Archon", "Solar", "Deva", "Planetar"]),
        ("Fey", ["Pixie", "Satyr", "Dryad", "Nymph", "Faerie Dragon"]),
        ("Giant", ["Hill Giant", "Stone Giant", "Frost Giant", "Fire Giant", "Cloud Giant"]),
        ("Humanoid", ["Bandit", "Cultist", "Assassin", "Warlock", "Necromancer"]),
        ("Monstrosity", ["Chimera", "Manticore", "Gorgon", "Minotaur", "Griffon"]),
        ("Ooze", ["Slime", "Gelatinous Cube", "Black Pudding", "Gray Ooze", "Ochre Jelly"]),
        ("Fiend", ["Devil", "Balor", "Pit Fiend", "Erinyes", "Bone Devil"]),
        ("Underdark", ["Drow", "Duergar", "Deep Gnome", "Troglodyte", "Hook Horror"]),
        ("Arctic", ["Yeti", "White Wolf", "Ice Troll", "Frost Wurm", "Abominable Snowman"]),
        ("Desert", ["Sand Worm", "Mummy", "Dust Devil", "Sandling", "Desert Drake"]),
        ("Swamp", ["Bog Beast", "Crocodilian", "Marsh Troll", "Swamp Thing", "Rot Grub"]),
        ("Mountain", ["Mountain Lion", "Cave Bear", "Rock Troll", "Cliff Racer", "Storm Giant"]),
        ("Forest", ["Dire Wolf", "Owlbear", "Displacer Beast", "Forest Drake", "Green Dragon"]),
        ("Volcanic", ["Magma Elemental", "Fire Drake", "Lava Troll", "Salamander", "Efreet"]),
        ("Shadow", ["Shadow Beast", "Shade", "Nightwalker", "Dark One", "Void Creature"]),
        ("Ethereal", ["Ghost Dragon", "Phase Spider", "Ethereal Filcher", "Nightmare", "Astral Deva"]),
        ("Planar", ["Chaos Beast", "Gith", "Modron", "Slaad", "Titan"]),
    ]
    
    for enemy_type, names in enemy_templates:
        enemies["enemy_types"].append({
            "type": enemy_type,
            "names": names,
            "base_stats": {
                "health_range": [40 + random.randint(0, 20), 60 + random.randint(0, 40)],
                "mana_range": [30 + random.randint(0, 20), 50 + random.randint(0, 50)],
                "level_range": [1 + random.randint(0, 2), 5 + random.randint(0, 10)]
            },
            "attacks": {
                "melee": [
                    {
                        "name": f"{random.choice(['Slash', 'Strike', 'Crush', 'Bite', 'Claw'])}",
                        "damage": [8 + random.randint(0, 5), 15 + random.randint(0, 10)],
                        "mana_cost": 5 + random.randint(0, 5),
                        "miss_chance": 0.15,
                        "crit_chance": 0.1
                    }
                ],
                "magic": [
                    {
                        "name": f"{random.choice(['Fireball', 'Ice Shard', 'Lightning', 'Dark Bolt', 'Arcane Blast'])}",
                        "damage": [12 + random.randint(0, 5), 20 + random.randint(0, 10)],
                        "mana_cost": 15 + random.randint(0, 5),
                        "miss_chance": 0.25,
                        "crit_chance": 0.15
                    }
                ]
            }
        })
    
    # Add affixes
    prefixes = [
        ("Fierce", {"damage": 1.15, "health": 1.05}),
        ("Tough", {"health": 1.2, "damage": 0.95}),
        ("Magical", {"mana": 1.2, "magic_damage": 1.15}),
        ("Swift", {"miss_chance": 0.85, "crit_chance": 1.15}),
        ("Ancient", {"health": 1.25, "mana": 1.25, "damage": 1.1}),
        ("Savage", {"damage": 1.3, "crit_chance": 1.2}),
        ("Armored", {"health": 1.15, "defense": 1.25}),
        ("Berserker", {"damage": 1.4, "health": 0.8}),
        ("Cunning", {"crit_chance": 1.3, "miss_chance": 0.9}),
        ("Massive", {"health": 1.5, "damage": 1.2}),
    ]
    
    suffixes = [
        ("of Darkness", {"magic_damage": 1.2}),
        ("of the Mountain", {"health": 1.3}),
        ("of Rage", {"damage": 1.25, "crit_chance": 1.2}),
        ("of Wisdom", {"mana": 1.3, "magic_damage": 1.15}),
        ("of Speed", {"miss_chance": 0.8}),
        ("of Power", {"damage": 1.3, "magic_damage": 1.3}),
        ("of Protection", {"health": 1.2, "defense": 1.3}),
        ("of Destruction", {"damage": 1.5}),
        ("of the Void", {"magic_damage": 1.4, "mana": 1.4}),
        ("of Eternity", {"health": 1.4, "mana": 1.4, "damage": 1.2}),
    ]
    
    for name, multipliers in prefixes:
        enemies["affixes"]["prefixes"].append({
            "name": name,
            "stat_multipliers": multipliers
        })
    
    for name, multipliers in suffixes:
        enemies["affixes"]["suffixes"].append({
            "name": name,
            "stat_multipliers": multipliers
        })
    
    return enemies

# Generate and save files
print("Generating expanded configurations...")

print("Expanding items to 100...")
items = expand_items_to_100()
with open('src/config/items.yaml', 'w') as f:
    yaml.dump(items, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

print("Expanding quests to 50...")
quests = expand_quests_to_50()
with open('src/config/quests.yaml', 'w') as f:
    yaml.dump(quests, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

print("Expanding enemies to 150...")
enemies = expand_enemies_to_150()
with open('src/config/enemies.yaml', 'w') as f:
    yaml.dump(enemies, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

print("\nConfiguration expansion complete!")
print(f"Items: {len(items['items'])} items")
print(f"Quests: {sum(len(chain['quests']) for chain in quests['quest_chains'])} quests across {len(quests['quest_chains'])} chains")
print(f"Enemies: {len(enemies['enemy_types'])} enemy types with {len(enemies['affixes']['prefixes'])} prefixes and {len(enemies['affixes']['suffixes'])} suffixes")
print(f"Total possible enemy combinations: {len(enemies['enemy_types']) * 5 * (1 + len(enemies['affixes']['prefixes']) + len(enemies['affixes']['suffixes']) + len(enemies['affixes']['prefixes']) * len(enemies['affixes']['suffixes']))}")
