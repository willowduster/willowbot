from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
import random

@dataclass
class Attack:
    name: str
    damage_range: Tuple[int, int]
    mana_cost: int
    miss_chance: float
    crit_chance: float
    attack_type: str  # 'melee' or 'magic'

    def execute(self, attacker: 'CombatEntity', defender: 'CombatEntity') -> Dict[str, any]:
        """Execute the attack and return the result"""
        if attacker.mana < self.mana_cost:
            return {
                'success': False,
                'message': f'{attacker.name} doesn\'t have enough mana!',
                'damage': 0
            }

        # Deduct mana cost
        attacker.mana -= self.mana_cost

        # Check for miss
        if random.random() < self.miss_chance:
            return {
                'success': False,
                'message': f'{attacker.name}\'s {self.name} missed!',
                'damage': 0
            }

        # Calculate base damage
        base_damage = random.randint(*self.damage_range)
        
        # Apply equipment damage bonuses
        if self.attack_type == 'magic':
            base_damage += attacker.magic_damage_bonus
        else:
            base_damage += attacker.damage_bonus
            
        # Check for critical hit with equipment bonus
        total_crit_chance = self.crit_chance * attacker.crit_chance_multiplier + attacker.crit_chance_bonus
        is_crit = random.random() < total_crit_chance
        damage = base_damage * 2 if is_crit else base_damage

        # Apply damage multipliers from affixes
        if hasattr(attacker, 'damage_multiplier'):
            damage *= attacker.damage_multiplier
        if self.attack_type == 'magic' and hasattr(attacker, 'magic_damage_multiplier'):
            damage *= attacker.magic_damage_multiplier

        # Apply defender's defense
        if self.attack_type == 'magic':
            damage = max(0, damage - defender.magic_defense)
        else:
            damage = max(0, damage - defender.defense)

        # Round the final damage
        damage = round(damage)
        defender.health = max(0, defender.health - damage)

        return {
            'success': True,
            'message': f'{attacker.name} used {self.name}{"(Critical Hit!)" if is_crit else ""}',
            'damage': damage,
            'is_crit': is_crit
        }

@dataclass
class CombatEntity:
    name: str
    health: int
    max_health: int
    mana: int
    max_mana: int
    level: int
    attacks: List[Attack]
    damage_multiplier: float = 1.0
    magic_damage_multiplier: float = 1.0
    miss_chance_multiplier: float = 1.0
    crit_chance_multiplier: float = 1.0
    
    # Equipment bonuses
    damage_bonus: int = 0
    magic_damage_bonus: int = 0
    defense: int = 0
    magic_defense: int = 0
    crit_chance_bonus: float = 0
    flee_chance_bonus: float = 0

    def try_flee(self, base_flee_chance: float = 0.3) -> bool:
        """
        Attempt to flee from combat
        Args:
            base_flee_chance: Base chance of successful flee (0.0 to 1.0)
        Returns:
            bool: True if flee successful, False otherwise
        """
        total_flee_chance = base_flee_chance + self.flee_chance_bonus
        return random.random() < total_flee_chance

    def is_alive(self) -> bool:
        return self.health > 0

    def regenerate_mana(self, percentage: float = 0.2):
        """Regenerate mana by percentage of max_mana"""
        regen_amount = round(self.max_mana * percentage)
        self.mana = min(self.max_mana, self.mana + regen_amount)
        return regen_amount

    def get_status(self) -> Dict[str, any]:
        return {
            'name': self.name,
            'health': self.health,
            'max_health': self.max_health,
            'mana': self.mana,
            'max_mana': self.max_mana,
            'level': self.level
        }