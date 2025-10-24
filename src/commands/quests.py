import discord
from discord.ext import commands
from ..models.quest_manager import QuestManager
from ..models.enemy import EnemyGenerator

class QuestCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_manager = QuestManager(bot)
        self.enemy_generator = EnemyGenerator()

    @commands.command(name='quests')
    async def list_quests(self, ctx):
        """List available quests"""
        available_quests = await self.quest_manager.get_available_quests(ctx.author.id)
        
        if not available_quests:
            await ctx.send("No quests available right now!")
            return

        embed = discord.Embed(
            title="📜 Available Quests",
            color=discord.Color.blue()
        )

        for quest in available_quests:
            # Create quest description
            objectives_text = "\n".join([
                f"- {obj.description}" for obj in quest.objectives
            ])
            rewards_text = f"Rewards:\n- {quest.rewards.xp} XP\n- {quest.rewards.gold} Gold"
            if quest.rewards.items:
                rewards_text += "\n" + "\n".join([
                    f"- {item['count']}x {self.quest_manager.items[item['id']].name}"
                    for item in quest.rewards.items
                ])
            if quest.rewards.title:
                rewards_text += f"\n- Title: {self.quest_manager.titles[quest.rewards.title].name}"

            embed.add_field(
                name=f"{quest.title} (ID: {quest.id})",
                value=f"{quest.description}\n\n**Objectives:**\n{objectives_text}\n\n**{rewards_text}**",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name='start_quest')
    async def start_quest(self, ctx, quest_id: str):
        """Start a specific quest"""
        quest = await self.quest_manager.start_quest(ctx.author.id, quest_id)
        
        if not quest:
            await ctx.send("Invalid quest ID or quest is already active!")
            return

        embed = discord.Embed(
            title=f"📜 Quest Started: {quest.title}",
            description=quest.description,
            color=discord.Color.green()
        )

        objectives_text = "\n".join([
            f"- {obj.description} (0/{obj.count})" for obj in quest.objectives
        ])
        embed.add_field(
            name="Objectives",
            value=objectives_text,
            inline=False
        )

        if quest.type == "combat":
            # Start first combat if it's a combat quest
            first_objective = quest.objectives[0]
            if first_objective.type.value.startswith('combat'):
                enemy = self.enemy_generator.generate_enemy(
                    ctx.author.level,
                    enemy_type=first_objective.enemy_type,
                    enemy_prefix=first_objective.enemy_prefix,
                    enemy_suffix=first_objective.enemy_suffix
                )
                await self.bot.get_cog('CombatCommands').start_combat(ctx, enemy)
        
        await ctx.send(embed=embed)

    @commands.command(name='quest_progress')
    async def quest_progress(self, ctx):
        """Check your current quest progress"""
        async with self.bot.db.execute(
            '''SELECT quest_id, objectives_progress, completed, rewards_claimed
               FROM active_quests 
               WHERE player_id = ?''',
            (ctx.author.id,)
        ) as cursor:
            active_quests = await cursor.fetchall()

        if not active_quests:
            await ctx.send("You have no active quests!")
            return

        embed = discord.Embed(
            title="📋 Quest Progress",
            color=discord.Color.blue()
        )

        for quest_id, objectives_progress, completed, rewards_claimed in active_quests:
            quest = self.quest_manager.quests[quest_id]
            progress = json.loads(objectives_progress)
            
            status = "✅ Complete" if completed else "⏳ In Progress"
            if completed and rewards_claimed:
                status += " (Rewards Claimed)"
            elif completed:
                status += " (Rewards Available!)"

            objectives_text = "\n".join([
                f"- {obj.description} ({progress[i]}/{obj.count})"
                for i, obj in enumerate(quest.objectives)
            ])

            embed.add_field(
                name=f"{quest.title} - {status}",
                value=f"{quest.description}\n\n**Objectives:**\n{objectives_text}",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name='claim_rewards')
    async def claim_rewards(self, ctx, quest_id: str):
        """Claim rewards for a completed quest"""
        rewards = await self.quest_manager.claim_quest_rewards(ctx.author.id, quest_id)
        
        if not rewards:
            await ctx.send("No rewards to claim! Make sure the quest is complete and hasn't been claimed already.")
            return

        embed = discord.Embed(
            title="🎁 Quest Rewards Claimed!",
            description=f"You received:",
            color=discord.Color.gold()
        )

        rewards_text = [
            f"• {rewards.xp} XP",
            f"• {rewards.gold} Gold"
        ]

        if rewards.items:
            for item in rewards.items:
                item_name = self.quest_manager.items[item['id']].name
                rewards_text.append(f"• {item['count']}x {item_name}")

        if rewards.title:
            title = self.quest_manager.titles[rewards.title]
            rewards_text.append(f"• Title: {title.name}")

        embed.add_field(
            name="Rewards",
            value="\n".join(rewards_text),
            inline=False
        )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(QuestCommands(bot))