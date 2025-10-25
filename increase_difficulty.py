#!/usr/bin/env python3
"""
Increase enemy difficulty slightly to make combat more challenging.
"""
import yaml

def increase_difficulty(config_path='src/config/enemies.yaml'):
    """Increase enemy stats to make them slightly harder"""
    
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Increase base enemy stats by 15%
    for enemy in data['enemy_types']:
        # Increase health
        enemy['base_stats']['health_range'] = [
            int(h * 1.15) for h in enemy['base_stats']['health_range']
        ]
        # Increase mana
        enemy['base_stats']['mana_range'] = [
            int(m * 1.15) for m in enemy['base_stats']['mana_range']
        ]
        
        # Increase damage for all attacks
        for attack_type in ['melee', 'magic']:
            if attack_type in enemy['attacks']:
                for attack in enemy['attacks'][attack_type]:
                    attack['damage'] = [
                        int(d * 1.15) for d in attack['damage']
                    ]
                    # Decrease miss chance slightly (make them hit more)
                    attack['miss_chance'] = max(0.15, attack['miss_chance'] * 0.85)
                    # Slightly increase crit chance
                    attack['crit_chance'] = min(0.20, attack['crit_chance'] * 1.15)
    
    # Increase affix multipliers
    for prefix in data['affixes']['prefixes']:
        for stat, multiplier in prefix['stat_multipliers'].items():
            if stat in ['damage', 'magic_damage', 'health', 'mana', 'defense']:
                # Increase boost multipliers (>1.0)
                if multiplier > 1.0:
                    prefix['stat_multipliers'][stat] = 1.0 + (multiplier - 1.0) * 1.15
            elif stat == 'crit_chance':
                # Increase crit chance boosts
                if multiplier > 1.0:
                    prefix['stat_multipliers'][stat] = 1.0 + (multiplier - 1.0) * 1.15
    
    for suffix in data['affixes']['suffixes']:
        for stat, multiplier in suffix['stat_multipliers'].items():
            if stat in ['damage', 'magic_damage', 'health', 'mana', 'defense']:
                if multiplier > 1.0:
                    suffix['stat_multipliers'][stat] = 1.0 + (multiplier - 1.0) * 1.15
            elif stat == 'crit_chance':
                if multiplier > 1.0:
                    suffix['stat_multipliers'][stat] = 1.0 + (multiplier - 1.0) * 1.15
    
    # Write back
    with open(config_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print("✅ Enemy difficulty increased!")
    print("   - Base health: +15%")
    print("   - Base mana: +15%")
    print("   - Attack damage: +15%")
    print("   - Miss chance: -15% (enemies hit more)")
    print("   - Crit chance: +15%")
    print("   - Affix bonuses: +15%")

if __name__ == '__main__':
    increase_difficulty()
