import json
import discord
import logging
import asyncio
from discord.ext import commands
from ..models.quest_manager import QuestManager
from ..models.inventory_manager import InventoryManager
from ..models.enemy import EnemyGenerator
from ..models.quest import QuestType

logger = logging.getLogger('willowbot.quests')

class QuestCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_manager = QuestManager(bot)
        self.inventory_manager = InventoryManager(bot)
        self.enemy_generator = EnemyGenerator()
        self.quest_pages = {}

    def get_quest_embed(self, quest, page_num, total_pages):
        """Create an embed for a single quest"""
        embed = discord.Embed(
            title=f"📜 Quest Details ({page_num + 1}/{total_pages})",
            description=quest.title,
            color=discord.Color.blue()
        )

        # Create quest description
        objectives_text = "\n".join([
            f"- {obj.description}" for obj in quest.objectives
        ])
        rewards_text = f"Rewards:\n- {quest.rewards.xp} XP\n- {quest.rewards.gold} Gold"
        if quest.rewards.items:
            rewards_text += "\n" + "\n".join([
                f"- {item['count']}x {self.inventory_manager.items[item['id']].name}"
                for item in quest.rewards.items
            ])
        if quest.rewards.title:
            rewards_text += f"\n- Title: {self.quest_manager.titles[quest.rewards.title].name}"

        embed.add_field(name="Description", value=quest.description, inline=False)
        embed.add_field(name="Objectives", value=objectives_text, inline=False)
        embed.add_field(name="Rewards", value=rewards_text, inline=False)

        # Add footer with controls help
        embed.set_footer(text="▶️ Start Quest | ❌ Cancel")
        return embed

    @commands.command(name='quests', aliases=['q'])
    async def list_quests(self, ctx):
        """List available quests with reaction controls"""
        logger.info(f"Listing quests for user {ctx.author.id}")
        available_quests = await self.quest_manager.get_available_quests(ctx.author.id)
        
        if not available_quests:
            logger.info(f"No quests available for user {ctx.author.id}")
            await ctx.send("No quests available right now!")
            return
        
        logger.info(f"Found {len(available_quests)} available quests for user {ctx.author.id}")

        # Store quests in a list for pagination
        self.quest_pages = {}
        self.quest_pages[ctx.author.id] = {
            'quests': available_quests,
            'current_page': 0
        }
        
        # Send initial embed
        current_quest = available_quests[0]
        embed = self.get_quest_embed(current_quest, 0, len(available_quests))
        message = await ctx.send(embed=embed)
        
        # Store message ID
        self.quest_pages[ctx.author.id]['message_id'] = message.id
        
        # Add reaction controls
        await message.add_reaction("▶️")   # Start
        await message.add_reaction("❌")   # Cancel

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle quest navigation and selection via reactions"""
        if user.bot:
            return

        message = reaction.message
        # Check if this is a quest message we're tracking
        if not any(pages.get('message_id') == message.id for pages in self.quest_pages.values()):
            return

        # Find the user's quest pages
        user_pages = next(
            (pages for user_id, pages in self.quest_pages.items() if pages.get('message_id') == message.id),
            None
        )
        if not user_pages:
            return

        quests = user_pages['quests']
        current_page = user_pages['current_page']

        # Try to remove user's reaction if we have permission
        try:
            await reaction.remove(user)
        except discord.Forbidden:
            pass  # Bot doesn't have permission to manage reactions
        except Exception:
            pass  # Other errors shouldn't stop the command from working

        emoji = str(reaction.emoji)
        if emoji == "▶️":  # Start quest
            logger.info(f"User {user.id} attempting to start quest")
            quest = quests[current_page]
            logger.info(f"Starting quest {quest.id} for user {user.id}")
            # Start the quest
            started_quest = await self.quest_manager.start_quest(user.id, quest.id)
            if not started_quest:
                logger.warning(f"Quest {quest.id} unavailable for user {user.id}")
                await message.channel.send("This quest is unavailable!", delete_after=5)
                return
            logger.info(f"Successfully started quest {quest.id} for user {user.id}")

            try:
                logger.info("=== ENTERING TRY BLOCK ===")
                # Get the current progress
                progress = getattr(started_quest, 'objectives_progress', [0] * len(started_quest.objectives))
                logger.info(f"Got progress: {progress}")
                
                # Get the first objective
                first_objective = started_quest.objectives[0]
                logger.info(f"Got first objective: {first_objective}")
                
                logger.info(f"About to check quest type. Quest object: {started_quest}")
                logger.info(f"Started quest type: {started_quest.type if hasattr(started_quest, 'type') else 'NO TYPE ATTR'}")
                logger.info(f"Original quest type: {quest.type if hasattr(quest, 'type') else 'NO TYPE ATTR'}")
            except Exception as e:
                logger.error(f"Error getting quest info: {str(e)}", exc_info=True)
                await message.channel.send(f"Error starting quest: {str(e)}")
                return

            # Try to clean up the old message first
            old_msg = None
            try:
                # Try to clear reactions first
                await message.clear_reactions()
                # Then update the message
                progress_embed = discord.Embed(
                    title="Quest Started!",
                    description=f"Preparing your quest: {quest.title}",
                    color=discord.Color.green()
                )
                old_msg = await message.edit(embed=progress_embed)
            except Exception as e:
                logger.warning(f"Could not update quest message: {str(e)}")

            # Start or resume combat if the quest has combat objectives
            logger.info(f"Quest type: {started_quest.type}")
            first_objective = started_quest.objectives[0]
            current_progress = progress[0] if progress else 0
            logger.info(f"First objective type: {first_objective.type.value}, progress: {current_progress}, count: {first_objective.count}")
            
            # Check if this objective requires combat (regardless of quest type)
            if first_objective.type.value.startswith('combat') and current_progress < first_objective.count:
                logger.info(f"Combat conditions met, starting combat")
                # Get combat cog
                combat_cog = self.bot.get_cog('CombatCommands')
                if not combat_cog:
                    logger.error("Combat cog not found!")
                    await message.channel.send("❌ There was an error initializing combat. Please try again.")
                    return
                
                # If we managed to keep the old message, delete it after sending the new one
                if old_msg:
                    try:
                        await old_msg.delete()
                    except Exception as e:
                        logger.warning(f"Could not delete old quest message: {str(e)}")
                    
                try:
                    # Start combat directly - no need for intermediate message
                    logger.info(f"Calling start_quest_combat for user {user.id} in channel {message.channel}")
                    combat_msg = await combat_cog.start_quest_combat(message.channel, user.id)
                    logger.info(f"start_quest_combat returned: {combat_msg}")
                    if combat_msg:
                        logger.info(f"✅ Combat started successfully for user {user.id}")
                    else:
                        logger.error(f"❌ start_quest_combat returned None for user {user.id}")
                        await message.channel.send("❌ Combat could not be started. Please check the logs or try `!w quests` again.")
                except Exception as e:
                    logger.error(f"❌ Exception while starting combat: {str(e)}", exc_info=True)
                    await message.channel.send(f"❌ Error starting combat: {str(e)}\nPlease try again or contact an admin.")
            else:
                # For objectives that don't require combat, just send the quest info
                quest_embed = discord.Embed(
                    title="Quest Started!",
                    description=f"**{quest.title}**\n{quest.description}",
                    color=discord.Color.green()
                )
                await message.channel.send(embed=quest_embed)
                
                # If we managed to keep the old message, delete it
                if old_msg:
                    try:
                        await old_msg.delete()
                    except Exception as e:
                        logger.warning(f"Could not delete old quest message: {str(e)}")
            
            del self.quest_pages[user.id]
            return
        elif emoji == "❌":  # Close quest viewer
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                try:
                    # If we can't delete, try to edit it to show it's closed
                    embed = discord.Embed(
                        title="Quest Viewer Closed",
                        description="This quest viewer has been closed.",
                        color=discord.Color.dark_grey()
                    )
                    await message.edit(embed=embed)
                    await message.clear_reactions()
                except (discord.Forbidden, discord.NotFound):
                    pass  # Message might be already gone or we lack permissions
            del self.quest_pages[user.id]
            return

        # Update current page and edit message
        user_pages['current_page'] = current_page
        quest = quests[current_page]
        embed = self.get_quest_embed(quest, current_page, len(quests))
        await message.edit(embed=embed)

    @commands.command(name='start_quest')
    async def start_quest(self, ctx, quest_id: str = None):
        """Show available quests or start a specific quest (Legacy command)"""
        await ctx.send("Use the `!quests` command to view and start quests using the new reaction interface!")
        await self.list_quests(ctx)

    @commands.command(name='quest_progress')
    async def quest_progress(self, ctx):
        """Check your current quest progress"""
        async with await self.bot.db_connect() as db:
            async with db.execute(
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
                item_name = self.inventory_manager.items[item['id']].name
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