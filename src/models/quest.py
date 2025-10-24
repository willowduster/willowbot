from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum

class QuestType(Enum):
    COMBAT = "combat"
    BOSS_COMBAT = "boss_combat"

class ObjectiveType(Enum):
    COMBAT = "combat"
    COMBAT_WITH_ATTACK = "combat_with_attack"

@dataclass
class QuestObjective:
    type: ObjectiveType
    description: str
    count: int
    current_progress: int = 0
    enemy_type: Optional[str] = None
    enemy_prefix: Optional[str] = None
    enemy_suffix: Optional[str] = None
    attack_type: Optional[str] = None

    def is_complete(self) -> bool:
        return self.current_progress >= self.count

    def update_progress(self, amount: int = 1):
        self.current_progress = min(self.count, self.current_progress + amount)

@dataclass
class QuestReward:
    xp: int
    gold: int
    items: List[Dict[str, int]]  # List of {item_id: count}
    title: Optional[str] = None

@dataclass
class Quest:
    id: str
    title: str
    description: str
    type: QuestType
    objectives: List[QuestObjective]
    rewards: QuestReward
    requirements: Dict[str, any]
    next_quest: Optional[str] = None
    
    def is_complete(self) -> bool:
        return all(obj.is_complete() for obj in self.objectives)

@dataclass
class QuestChain:
    id: str
    name: str
    description: str
    quests: List[Quest]
    requirements: Optional[Dict[str, any]] = None

@dataclass
class PlayerQuest:
    quest_id: str
    objectives: List[QuestObjective]
    completed: bool = False
    rewards_claimed: bool = False

@dataclass
class QuestItem:
    id: str
    name: str
    description: str
    effect: Dict[str, any]
    value: int

@dataclass
class Title:
    id: str
    name: str
    description: str
    bonuses: Dict[str, float]