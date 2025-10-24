from dataclasses import dataclass
from typing import Dict, Optional
from enum import Enum

class ItemType(Enum):
    CONSUMABLE = "consumable"
    WEAPON = "weapon"
    HELMET = "helmet"
    ARMOR = "armor"
    PANTS = "pants"
    BOOTS = "boots"
    RING = "ring"
    AMULET = "amulet"
    MATERIAL = "material"
    QUEST = "quest"

class ItemRarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"

    @property
    def color_code(self) -> int:
        return {
            "common": 0x969696,      # Gray
            "uncommon": 0x1eff00,    # Green
            "rare": 0x0070dd,        # Blue
            "epic": 0xa335ee,        # Purple
            "legendary": 0xff8000,   # Orange
        }[self.value]

@dataclass
class ItemEffect:
    type: str
    value: int
    duration: Optional[int] = None  # For consumables
    target_type: Optional[str] = None  # For specific enemy type bonuses

@dataclass
class Item:
    id: str
    name: str
    description: str
    type: ItemType
    rarity: ItemRarity
    level_requirement: int
    effects: list[ItemEffect]
    value: int
    stackable: bool = True
    max_stack: int = 99

@dataclass
class InventorySlot:
    item: Item
    count: int

class Inventory:
    def __init__(self, player_id: int, level: int):
        self.player_id = player_id
        self.level = level
        self.slots: Dict[str, InventorySlot] = {}
        self.max_slots = self._calculate_max_slots(level)

    def _calculate_max_slots(self, level: int) -> int:
        """Calculate max inventory slots based on player level"""
        # Start with 20 slots, gain 2 slots every 5 levels
        base_slots = 20
        bonus_slots = (level // 5) * 2
        return base_slots + bonus_slots

    def has_space(self) -> bool:
        """Check if inventory has space for new items"""
        return len(self.slots) < self.max_slots

    def has_item(self, item_id: str) -> bool:
        """Check if inventory has a specific item"""
        return item_id in self.slots

    def can_add_item(self, item: Item, count: int = 1) -> bool:
        """Check if an item can be added to inventory"""
        if not self.has_space() and not self.has_item(item.id):
            return False
        
        if item.id in self.slots:
            current_count = self.slots[item.id].count
            if not item.stackable or current_count + count > item.max_stack:
                return self.has_space()
        
        return True

    def add_item(self, item: Item, count: int = 1) -> bool:
        """Add an item to inventory"""
        if not self.can_add_item(item, count):
            return False

        if item.id in self.slots:
            self.slots[item.id].count += count
            if self.slots[item.id].count > item.max_stack:
                overflow = self.slots[item.id].count - item.max_stack
                self.slots[item.id].count = item.max_stack
                # Create new stack for overflow if there's space
                if self.has_space():
                    self.slots[f"{item.id}_overflow"] = InventorySlot(item, overflow)
                else:
                    return False
        else:
            self.slots[item.id] = InventorySlot(item, count)

        return True

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        """Remove an item from inventory"""
        if item_id not in self.slots:
            return False

        slot = self.slots[item_id]
        if slot.count < count:
            return False

        slot.count -= count
        if slot.count == 0:
            del self.slots[item_id]

        return True

    def get_item_count(self, item_id: str) -> int:
        """Get the count of a specific item"""
        return self.slots[item_id].count if item_id in self.slots else 0

    def update_max_slots(self, new_level: int):
        """Update inventory size when player levels up"""
        self.level = new_level
        self.max_slots = self._calculate_max_slots(new_level)