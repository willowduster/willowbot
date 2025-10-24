from dataclasses import dataclass

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