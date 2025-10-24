import yaml
import random
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from .inventory import Item, ItemType, ItemRarity, ItemEffect, Inventory, InventorySlot
from .equipment import EquipmentSlots

class LootTable:
    def __init__(self, enemy_type: str, level: int):
        self.enemy_type = enemy_type
        self.level = level
        
        # Rarity chances based on level
        self.rarity_chances = {
            ItemRarity.COMMON: 0.6 - (level * 0.02),      # Decreases with level
            ItemRarity.UNCOMMON: 0.25 + (level * 0.01),   # Increases slightly
            ItemRarity.RARE: 0.1 + (level * 0.01),        # Increases slightly
            ItemRarity.EPIC: 0.04 + (level * 0.005),      # Increases very slightly
            ItemRarity.LEGENDARY: 0.01 + (level * 0.005)  # Increases very slightly
        }

        # Normalize probabilities
        total = sum(self.rarity_chances.values())
        for rarity in self.rarity_chances:
            self.rarity_chances[rarity] /= total

    def roll_rarity(self) -> ItemRarity:
        """Roll for item rarity"""
        roll = random.random()
        cumulative = 0
        for rarity, chance in self.rarity_chances.items():
            cumulative += chance
            if roll <= cumulative:
                return rarity
        return ItemRarity.COMMON

class InventoryManager:
    def __init__(self, bot):
        self.bot = bot
        self.items_cache = {}
        self._load_items()

    def _load_items(self):
        """Load item data from YAML"""
        config_path = Path(__file__).parent.parent / 'config' / 'items.yaml'
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        self.items = {}
        for item_id, item_data in data['items'].items():
            effects = [
                ItemEffect(**effect_data)
                for effect_data in item_data.get('effects', [])
            ]
            
            self.items[item_data['id']] = Item(
                id=item_data['id'],
                name=item_data['name'],
                description=item_data['description'],
                type=ItemType(item_data['type']),
                rarity=ItemRarity(item_data['rarity']),
                level_requirement=item_data['level_requirement'],
                effects=effects,
                value=item_data['value'],
                stackable=item_data.get('stackable', True),
                max_stack=item_data.get('max_stack', 99)
            )

    async def get_inventory(self, player_id: int) -> Optional[Inventory]:
        """Get a player's inventory"""
        async with await self.bot.db_connect() as db:
            async with db.execute(
                'SELECT level FROM players WHERE id = ?',
                (player_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                
                level = row[0]
                inventory = Inventory(player_id, level)

            # Load inventory items
            async with db.execute(
                'SELECT item_id, count FROM inventory WHERE player_id = ?',
                (player_id,)
            ) as cursor:
                async for row in cursor:
                    item_id, count = row
                    if item_id in self.items:
                        inventory.slots[item_id] = InventorySlot(self.items[item_id], count)

            return inventory

    async def save_inventory(self, inventory: Inventory):
        """Save inventory to database"""
        async with await self.bot.db_connect() as db:
            await db.execute(
                'DELETE FROM inventory WHERE player_id = ?',
                (inventory.player_id,)
            )

            # Insert new inventory items
            for slot in inventory.slots.values():
                await db.execute(
                    'INSERT INTO inventory (player_id, item_id, count) VALUES (?, ?, ?)',
                    (inventory.player_id, slot.item.id, slot.count)
                )
            await db.commit()

    async def get_equipment(self, player_id: int) -> EquipmentSlots:
        """Get player's equipment"""
        equipment = EquipmentSlots()
        
        async with await self.bot.db_connect() as db:
            async with db.execute(
                'SELECT * FROM equipment WHERE player_id = ?',
                (player_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    # Create empty equipment entry if none exists
                    await db.execute(
                        'INSERT INTO equipment (player_id) VALUES (?)',
                        (player_id,)
                    )
                    await db.commit()
                    return equipment

            # Load equipped items
            columns = [desc[0] for desc in cursor.description]
            for i, value in enumerate(row):
                if value and columns[i].endswith('_id'):
                    slot_name = columns[i][:-3]  # Remove '_id' suffix
                    item = self.items.get(value)
                    if item:
                        setattr(equipment, slot_name, item)

        return equipment

    async def save_equipment(self, player_id: int, equipment: EquipmentSlots):
        """Save player's equipment"""
        async with await self.bot.db_connect() as db:
            await db.execute('''
                INSERT OR REPLACE INTO equipment (
                    player_id, helmet_id, armor_id, pants_id, boots_id,
                    weapon_id, ring1_id, ring2_id, amulet_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_id,
                equipment.helmet.id if equipment.helmet else None,
                equipment.armor.id if equipment.armor else None,
                equipment.pants.id if equipment.pants else None,
                equipment.boots.id if equipment.boots else None,
                equipment.weapon.id if equipment.weapon else None,
                equipment.ring1.id if equipment.ring1 else None,
                equipment.ring2.id if equipment.ring2 else None,
                equipment.amulet.id if equipment.amulet else None
            ))
            await db.commit()

        # Update player stats based on equipment
        await self.update_player_stats(player_id, equipment)

    async def update_player_stats(self, player_id: int, equipment: EquipmentSlots):
        """Update player's stats based on equipment"""
        stats = equipment.get_total_stats()
        
        async with await self.bot.db_connect() as db:
            # Get base stats (level-based)
            cursor = await db.execute(
                'SELECT level, health, mana FROM players WHERE id = ?',
                (player_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return
            
            level, current_health, current_mana = row
            
            # Calculate base max stats (from level)
            base_max_health = 100 + ((level - 1) * 10)
            base_max_mana = 100 + ((level - 1) * 5)
            
            # Apply equipment bonuses
            new_max_health = base_max_health + stats['health_bonus']
            new_max_mana = base_max_mana + stats['mana_bonus']
            
            # Update all stats including max health/mana
            await db.execute('''
                UPDATE players SET
                    max_health = ?,
                    max_mana = ?,
                    damage_bonus = ?,
                    magic_damage_bonus = ?,
                    defense = ?,
                    magic_defense = ?,
                    crit_chance_bonus = ?,
                    flee_chance_bonus = ?,
                    health_bonus = ?,
                    mana_bonus = ?
                WHERE id = ?
            ''', (
                new_max_health,
                new_max_mana,
                stats['damage'],
                stats['magic_damage'],
                stats['defense'],
                stats['magic_defense'],
                stats['crit_chance'],
                stats['flee_chance'],
                stats['health_bonus'],
                stats['mana_bonus'],
                player_id
            ))
            await db.commit()

    def generate_loot(self, enemy_type: str, enemy_level: int, is_boss: bool = False) -> List[Tuple[Item, int]]:
        """Generate loot drops based on enemy type and level"""
        loot_table = LootTable(enemy_type, enemy_level)
        num_items = random.randint(1, 3) if is_boss else random.randint(0, 2)
        loot = []

        for _ in range(num_items):
            rarity = loot_table.roll_rarity()
            
            # Filter suitable items based on enemy type, level, and rarity
            suitable_items = [
                item for item in self.items.values()
                if (item.level_requirement <= enemy_level + 2 and
                    item.level_requirement >= enemy_level - 3 and
                    item.rarity == rarity and
                    (enemy_type.lower() in item.description.lower() or
                     item.type in [ItemType.CONSUMABLE, ItemType.MATERIAL]))
            ]

            if suitable_items:
                item = random.choice(suitable_items)
                count = random.randint(1, 3) if item.stackable else 1
                loot.append((item, count))

        # Ensure boss always drops something
        if is_boss and not loot:
            # Get a rare or better item
            boss_items = [
                item for item in self.items.values()
                if (item.level_requirement <= enemy_level + 2 and
                    item.rarity in [ItemRarity.RARE, ItemRarity.EPIC, ItemRarity.LEGENDARY])
            ]
            if boss_items:
                item = random.choice(boss_items)
                loot.append((item, 1))

        return loot

    async def add_items(self, player_id: int, items: List[Tuple[Item, int]]) -> Tuple[List[Tuple[Item, int]], List[Tuple[Item, int]]]:
        """Add items to player's inventory, return (added_items, failed_items)"""
        inventory = await self.get_inventory(player_id)
        if not inventory:
            return [], items

        added = []
        failed = []
        for item, count in items:
            if inventory.add_item(item, count):
                added.append((item, count))
            else:
                failed.append((item, count))

        await self.save_inventory(inventory)
        return added, failed
    
    async def auto_equip_better_gear(self, player_id: int):
        """Automatically equip items from inventory if they're better than current equipment"""
        # Get current equipment
        equipment = await self.get_equipment(player_id)
        current_stats = equipment.get_total_stats()
        
        # Get inventory
        inventory = await self.get_inventory(player_id)
        if not inventory:
            return
        
        # Check each equipment slot
        equipped_any = False
        for slot_name in ['weapon', 'helmet', 'armor', 'pants', 'boots', 'ring1', 'ring2', 'amulet']:
            # Get current item in slot
            current_item = getattr(equipment, slot_name)
            
            # Find best item for this slot in inventory
            best_item = None
            best_score = self._calculate_item_score(current_item) if current_item else 0
            
            for item_id, slot in inventory.slots.items():
                item = slot.item
                
                # Check if item can go in this slot and player can use it
                if not equipment.can_equip(item, slot_name):
                    continue
                if item.level_requirement > inventory.level:
                    continue
                
                # For rings, skip if it's already equipped in the other ring slot
                if slot_name == 'ring2' and equipment.ring1 and equipment.ring1.id == item.id:
                    continue
                if slot_name == 'ring1' and equipment.ring2 and equipment.ring2.id == item.id:
                    continue
                
                # Calculate score for this item
                item_score = self._calculate_item_score(item)
                
                # If this item is better than current best, remember it
                if item_score > best_score:
                    best_item = item
                    best_score = item_score
            
            # If we found a better item, equip it
            if best_item and best_item != current_item:
                # Unequip current item back to inventory
                if current_item:
                    inventory.add_item(current_item, 1)
                
                # Remove new item from inventory
                if inventory.slots[best_item.id].count > 1:
                    inventory.slots[best_item.id].count -= 1
                else:
                    del inventory.slots[best_item.id]
                
                # Equip the new item
                equipment.equip(best_item, slot_name)
                equipped_any = True
        
        # Save changes if anything was equipped
        if equipped_any:
            await self.save_inventory(inventory)
            await self.save_equipment(player_id, equipment)
    
    def _calculate_item_score(self, item: Optional[Item]) -> float:
        """Calculate a score for an item based on its stats"""
        if not item or not item.effects:
            return 0.0
        
        score = 0.0
        stat_weights = {
            'damage': 2.0,
            'magic_damage': 2.0,
            'defense': 1.5,
            'magic_defense': 1.5,
            'health_bonus': 0.1,
            'mana_bonus': 0.05,
            'crit_chance': 3.0,
            'flee_chance': 0.5
        }
        
        for effect in item.effects:
            weight = stat_weights.get(effect.type, 1.0)
            score += effect.value * weight
        
        # Factor in rarity as a tie-breaker
        rarity_bonus = {
            ItemRarity.COMMON: 0,
            ItemRarity.UNCOMMON: 1,
            ItemRarity.RARE: 3,
            ItemRarity.EPIC: 6,
            ItemRarity.LEGENDARY: 10
        }
        score += rarity_bonus.get(item.rarity, 0)
        
        return score