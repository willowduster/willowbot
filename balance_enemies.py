#!/usr/bin/env python3
"""
Reduce enemy difficulty by adjusting stats and affixes.
"""
import yaml
import math

def reduce_stats(config_path='src/config/enemies.yaml'):
    """Reduce enemy stats to make them easier"""
    
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Reduce base enemy stats by 20%
    for enemy in data['enemy_types']:
        # Reduce health
        enemy['base_stats']['health_range'] = [
            max(20, int(h * 0.8)) for h in enemy['base_stats']['health_range']
        ]
        # Reduce mana
        enemy['base_stats']['mana_range'] = [
            max(15, int(m * 0.8)) for m in enemy['base_stats']['mana_range']
        ]
        
        # Reduce damage for all attacks
        for attack_type in ['melee', 'magic']:
            if attack_type in enemy['attacks']:
                for attack in enemy['attacks'][attack_type]:
                    attack['damage'] = [
                        max(5, int(d * 0.75)) for d in attack['damage']
                    ]
                    # Increase miss chance slightly (make them miss more)
                    attack['miss_chance'] = min(0.35, attack['miss_chance'] * 1.25)
                    # Reduce crit chance
                    attack['crit_chance'] = max(0.05, attack['crit_chance'] * 0.8)
    
    # Reduce affix multipliers
    for prefix in data['affixes']['prefixes']:
        for stat, multiplier in prefix['stat_multipliers'].items():
            if stat in ['damage', 'magic_damage', 'health', 'mana', 'defense']:
                # Reduce boost multipliers (>1.0)
                if multiplier > 1.0:
                    prefix['stat_multipliers'][stat] = 1.0 + (multiplier - 1.0) * 0.7
            elif stat == 'crit_chance':
                # Reduce crit chance boosts
                if multiplier > 1.0:
                    prefix['stat_multipliers'][stat] = 1.0 + (multiplier - 1.0) * 0.7
            elif stat == 'miss_chance':
                # Make penalties less severe (keep more reduction)
                if multiplier < 1.0:
                    prefix['stat_multipliers'][stat] = 1.0 - (1.0 - multiplier) * 0.7
    
    for suffix in data['affixes']['suffixes']:
        for stat, multiplier in suffix['stat_multipliers'].items():
            if stat in ['damage', 'magic_damage', 'health', 'mana', 'defense']:
                if multiplier > 1.0:
                    suffix['stat_multipliers'][stat] = 1.0 + (multiplier - 1.0) * 0.7
            elif stat == 'crit_chance':
                if multiplier > 1.0:
                    suffix['stat_multipliers'][stat] = 1.0 + (multiplier - 1.0) * 0.7
            elif stat == 'miss_chance':
                if multiplier < 1.0:
                    suffix['stat_multipliers'][stat] = 1.0 - (1.0 - multiplier) * 0.7
    
    # Write back
    with open(config_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    print("✅ Enemy difficulty reduced!")
    print("   - Base health: -20%")
    print("   - Base mana: -20%")
    print("   - Attack damage: -25%")
    print("   - Miss chance: +25% (enemies miss more)")
    print("   - Crit chance: -20%")
    print("   - Affix bonuses: -30%")

if __name__ == '__main__':
    reduce_stats()
