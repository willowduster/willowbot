import yaml
import random
from typing import Dict, List, Optional
from pathlib import Path
from .combat import Attack, CombatEntity

class EnemyGenerator:
    def __init__(self):
        config_path = Path(__file__).parent.parent / 'config' / 'enemies.yaml'
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def _apply_affixes(self, enemy_type: Dict, prefix: Optional[Dict] = None, suffix: Optional[Dict] = None) -> Dict[str, float]:
        """Apply prefix and suffix multipliers to the enemy"""
        multipliers = {
            'damage': 1.0,
            'magic_damage': 1.0,
            'health': 1.0,
            'mana': 1.0,
            'miss_chance': 1.0,
            'crit_chance': 1.0
        }

        if prefix:
            for stat, value in prefix['stat_multipliers'].items():
                multipliers[stat] = multipliers.get(stat, 1.0) * value

        if suffix:
            for stat, value in suffix['stat_multipliers'].items():
                multipliers[stat] = multipliers.get(stat, 1.0) * value

        return multipliers

    def generate_enemy(self, player_level: int) -> CombatEntity:
        """Generate a random enemy based on player level"""
        # Select random enemy type
        enemy_type = random.choice(self.config['enemy_types'])
        
        # Maybe apply affixes (70% chance)
        prefix = random.choice(self.config['affixes']['prefixes']) if random.random() < 0.7 else None
        suffix = random.choice(self.config['affixes']['suffixes']) if random.random() < 0.7 else None

        # Generate base stats
        base_stats = enemy_type['base_stats']
        level = max(1, min(
            random.randint(
                base_stats['level_range'][0],
                base_stats['level_range'][1]
            ),
            player_level + 2
        ))

        # Apply level scaling (10% increase per level)
        level_scale = 1 + (0.1 * (level - 1))

        # Get multipliers from affixes
        multipliers = self._apply_affixes(enemy_type, prefix, suffix)

        # Calculate final stats
        health = round(random.randint(*base_stats['health_range']) * level_scale * multipliers['health'])
        mana = round(random.randint(*base_stats['mana_range']) * level_scale * multipliers['mana'])

        # Generate attacks
        attacks = []
        if 'melee' in enemy_type.get('attacks', {}):
            for atk in enemy_type['attacks']['melee']:
                attacks.append(Attack(
                    name=atk['name'],
                    damage_range=(
                        round(atk['damage'][0] * level_scale),
                        round(atk['damage'][1] * level_scale)
                    ),
                    mana_cost=atk['mana_cost'],
                    miss_chance=atk['miss_chance'] * multipliers['miss_chance'],
                    crit_chance=atk['crit_chance'] * multipliers['crit_chance'],
                    attack_type='melee'
                ))

        if 'magic' in enemy_type.get('attacks', {}):
            for atk in enemy_type['attacks']['magic']:
                attacks.append(Attack(
                    name=atk['name'],
                    damage_range=(
                        round(atk['damage'][0] * level_scale),
                        round(atk['damage'][1] * level_scale)
                    ),
                    mana_cost=atk['mana_cost'],
                    miss_chance=atk['miss_chance'] * multipliers['miss_chance'],
                    crit_chance=atk['crit_chance'] * multipliers['crit_chance'],
                    attack_type='magic'
                ))

        # Generate name with affixes
        name_parts = []
        if prefix:
            name_parts.append(prefix['name'])
        name_parts.append(random.choice(enemy_type['names']))
        if suffix:
            name_parts.append(suffix['name'])

        return CombatEntity(
            name=' '.join(name_parts),
            health=health,
            max_health=health,
            mana=mana,
            max_mana=mana,
            level=level,
            attacks=attacks,
            damage_multiplier=multipliers['damage'],
            magic_damage_multiplier=multipliers['magic_damage'],
            miss_chance_multiplier=multipliers['miss_chance'],
            crit_chance_multiplier=multipliers['crit_chance']
        )