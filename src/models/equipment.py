from typing import Dict, Optional
from dataclasses import dataclass
from .inventory import Item, ItemType

@dataclass
class EquipmentSlots:
    helmet: Optional[Item] = None
    armor: Optional[Item] = None
    pants: Optional[Item] = None
    boots: Optional[Item] = None
    weapon: Optional[Item] = None
    ring1: Optional[Item] = None
    ring2: Optional[Item] = None
    amulet: Optional[Item] = None

    def get_total_stats(self) -> Dict[str, float]:
        """Calculate total stats from all equipped items"""
        total_stats = {
            'damage': 0,
            'magic_damage': 0,
            'defense': 0,
            'magic_defense': 0,
            'crit_chance': 0,
            'flee_chance': 0,
            'health_bonus': 0,
            'mana_bonus': 0
        }

        for slot in [self.helmet, self.armor, self.pants, self.boots, 
                    self.weapon, self.ring1, self.ring2, self.amulet]:
            if slot and slot.effects:
                for effect in slot.effects:
                    if effect.type in total_stats:
                        total_stats[effect.type] += effect.value

        return total_stats

    def can_equip(self, item: Item, slot_name: str) -> bool:
        """Check if an item can be equipped in the given slot"""
        slot_type_map = {
            'helmet': ItemType.HELMET,
            'armor': ItemType.ARMOR,
            'pants': ItemType.PANTS,
            'boots': ItemType.BOOTS,
            'weapon': ItemType.WEAPON,
            'ring1': ItemType.RING,
            'ring2': ItemType.RING,
            'amulet': ItemType.AMULET
        }
        return item.type == slot_type_map.get(slot_name)

    def equip(self, item: Item, slot_name: str) -> Optional[Item]:
        """
        Equip an item to a slot and return the previously equipped item if any
        """
        if not self.can_equip(item, slot_name):
            return None

        current_slot = getattr(self, slot_name)
        setattr(self, slot_name, item)
        return current_slot

    def unequip(self, slot_name: str) -> Optional[Item]:
        """
        Remove and return item from a slot
        """
        item = getattr(self, slot_name)
        setattr(self, slot_name, None)
        return item

    def to_dict(self) -> dict:
        """Convert equipment to dictionary for storage"""
        return {
            slot: (getattr(self, slot).id if getattr(self, slot) else None)
            for slot in ['helmet', 'armor', 'pants', 'boots', 'weapon', 
                        'ring1', 'ring2', 'amulet']
        }

    @classmethod
    def from_dict(cls, data: dict, item_lookup: Dict[str, Item]) -> 'EquipmentSlots':
        """Create equipment from dictionary and item lookup"""
        equipment = cls()
        for slot, item_id in data.items():
            if item_id and item_id in item_lookup:
                setattr(equipment, slot, item_lookup[item_id])
        return equipment