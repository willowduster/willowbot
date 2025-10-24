from dataclasses import dataclass
from typing import List, Optional
from .combat import Attack, CombatEntity

@dataclass
class Player:
    id: int  # Discord user ID
    name: str
    level: int = 1
    xp: int = 0
    health: int = 100
    max_health: int = 100
    mana: int = 100
    max_mana: int = 100
    in_combat: bool = False
    current_enemy: Optional[CombatEntity] = None
    damage_bonus: int = 0
    magic_damage_bonus: int = 0
    defense: int = 0
    magic_defense: int = 0
    crit_chance_bonus: float = 0.0
    flee_chance_bonus: float = 0.0
    health_bonus: int = 0
    mana_bonus: int = 0
    
    # Default player attacks
    basic_attacks: List[Attack] = None

    def __post_init__(self):
        if self.basic_attacks is None:
            self.basic_attacks = [
                Attack(
                    name="Slash",
                    damage_range=(15, 25),
                    mana_cost=10,
                    miss_chance=0.1,
                    crit_chance=0.15,
                    attack_type='melee'
                ),
                Attack(
                    name="Fireball",
                    damage_range=(20, 30),
                    mana_cost=25,
                    miss_chance=0.15,
                    crit_chance=0.2,
                    attack_type='magic'
                )
            ]
    
    def add_xp(self, amount: int) -> bool:
        """Add XP to the player and return True if leveled up"""
        self.xp += amount
        if self.xp >= self.xp_needed_for_next_level():
            self.level_up()
            return True
        return False
    
    def xp_needed_for_next_level(self) -> int:
        """Calculate XP needed for next level"""
        return self.level * 100
    
    def level_up(self):
        """Level up the player and increase stats"""
        self.level += 1
        self.max_health += 10
        self.health = self.max_health
        self.max_mana += 5
        self.mana = self.max_mana
        self.xp = 0  # Reset XP for next level