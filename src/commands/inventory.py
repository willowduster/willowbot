import discord
from discord.ext import commands
from ..models.inventory_manager import InventoryManager
from ..models.inventory import ItemType, ItemRarity
from ..models.equipment import EquipmentSlots

EQUIP_EMOJI = "🛡️"
DROP_EMOJI = "🗑️"
EQUIPMENT_SLOT_EMOJIS = {
    'helmet': '🪖',
    'armor': '🥋',
    'pants': '👖',
    'boots': '👢',
    'weapon': '⚔️',
    'ring1': '💍',
    'ring2': '💍',
    'amulet': '📿'
}

class InventoryCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.inventory_manager = InventoryManager(bot)
        self.pending_actions = {}

    @commands.command(name='equipment', aliases=['equip'])
    async def show_equipment(self, ctx):
        """Show your equipped items"""
        equipment = await self.inventory_manager.get_equipment(ctx.author.id)
        if not equipment:
            await ctx.send("You don't have a character yet! Use `!wb start` to create one.")
            return

        embed = discord.Embed(
            title=f"⚔️ {ctx.author.name}'s Equipment",
            color=discord.Color.gold()
        )

        # Show equipped items
        for slot_name, emoji in EQUIPMENT_SLOT_EMOJIS.items():
            item = getattr(equipment, slot_name)
            if item:
                rarity_prefix = "⚪" if item.rarity == ItemRarity.COMMON else \
                              "🟢" if item.rarity == ItemRarity.UNCOMMON else \
                              "🔵" if item.rarity == ItemRarity.RARE else \
                              "🟣" if item.rarity == ItemRarity.EPIC else "🟡"
                value = f"{rarity_prefix} {item.name} (Lvl {item.level_requirement})"
            else:
                value = "Empty"
            
            embed.add_field(
                name=f"{emoji} {slot_name.title()}",
                value=value,
                inline=True
            )

        # Add total stats
        stats = equipment.get_total_stats()
        stats_text = []
        for stat, value in stats.items():
            if value != 0:
                if stat in ['crit_chance', 'flee_chance']:
                    stats_text.append(f"{stat.replace('_', ' ').title()}: +{value}%")
                else:
                    stats_text.append(f"{stat.replace('_', ' ').title()}: +{value}")

        if stats_text:
            embed.add_field(
                name="📊 Total Stats",
                value="\n".join(stats_text),
                inline=False
            )

        message = await ctx.send(embed=embed)
        
        # Add reactions for unequipping items
        for slot_name, emoji in EQUIPMENT_SLOT_EMOJIS.items():
            if getattr(equipment, slot_name):
                await message.add_reaction(emoji)

        # Store the equipment message for reaction handling
        self.pending_actions[message.id] = {
            'type': 'equipment',
            'owner_id': ctx.author.id,
            'equipment': equipment
        }

    @commands.command(name='inventory', aliases=['inv'])
    async def show_inventory(self, ctx):
        """Show your inventory"""
        inventory = await self.inventory_manager.get_inventory(ctx.author.id)
        if not inventory:
            await ctx.send("You don't have a character yet! Use `!wb start` to create one.")
            return

        embed = discord.Embed(
            title=f"🎒 {ctx.author.name}'s Inventory ({len(inventory.slots)}/{inventory.max_slots} slots)",
            color=discord.Color.blue()
        )

        # Group items by type
        items_by_type = {}
        for slot in inventory.slots.values():
            item_type = slot.item.type.value
            if item_type not in items_by_type:
                items_by_type[item_type] = []
            items_by_type[item_type].append(slot)

        # Add items to embed by type
        for item_type in ItemType:
            if item_type.value not in items_by_type:
                continue

            items_text = []
            for slot in sorted(items_by_type[item_type.value], key=lambda x: x.item.name):
                rarity_prefix = "⚪" if slot.item.rarity == ItemRarity.COMMON else \
                              "🟢" if slot.item.rarity == ItemRarity.UNCOMMON else \
                              "🔵" if slot.item.rarity == ItemRarity.RARE else \
                              "🟣" if slot.item.rarity == ItemRarity.EPIC else "🟡"
                
                count_text = f" x{slot.count}" if slot.count > 1 else ""
                level_text = f" (Lvl {slot.item.level_requirement})" if slot.item.level_requirement > 1 else ""
                items_text.append(f"{rarity_prefix} {slot.item.name}{count_text}{level_text}")

            if items_text:
                embed.add_field(
                    name=f"📦 {item_type.value.title()}",
                    value="\n".join(items_text),
                    inline=False
                )

        await ctx.send(embed=embed)

    @commands.command(name='item')
    async def show_item_details(self, ctx, *, item_name: str):
        """Show detailed information about an item"""
        inventory = await self.inventory_manager.get_inventory(ctx.author.id)
        if not inventory:
            await ctx.send("You don't have a character yet! Use `!wb start` to create one.")
            return

        # Find item in inventory
        item = None
        for slot in inventory.slots.values():
            if slot.item.name.lower() == item_name.lower():
                item = slot.item
                count = slot.count
                break

        if not item:
            await ctx.send(f"You don't have an item called '{item_name}'.")
            return

        embed = discord.Embed(
            title=f"{item.name}",
            description=item.description,
            color=item.rarity.color_code
        )

        # Add rarity and type
        embed.add_field(
            name="Details",
            value=f"Rarity: {item.rarity.value.title()}\n"
                  f"Type: {item.type.value.title()}\n"
                  f"Level Required: {item.level_requirement}",
            inline=False
        )

        # Add effects
        if item.effects:
            effects_text = []
            for effect in item.effects:
                if effect.type in ['damage', 'magic_damage']:
                    effects_text.append(f"➕ {effect.value} {effect.type.replace('_', ' ').title()}")
                elif effect.type in ['heal', 'mana']:
                    effects_text.append(f"💟 Restores {effect.value} {effect.type.title()}")
                elif effect.type.endswith('_damage'):
                    target = effect.type.replace('_damage', '').title()
                    effects_text.append(f"⚔️ +{effect.value}% damage vs {target}")
                elif effect.type == 'crit_chance':
                    effects_text.append(f"🎯 +{effect.value}% Critical Hit Chance")
                else:
                    effects_text.append(f"✨ {effect.type.replace('_', ' ').title()}: {effect.value}")

            embed.add_field(
                name="Effects",
                value="\n".join(effects_text),
                inline=False
            )

        # Add value and count
        embed.add_field(
            name="Other",
            value=f"Value: {item.value} gold\n"
                  f"Count: {count}\n"
                  f"{'Stackable' if item.stackable else 'Not Stackable'}",
            inline=False
        )

        # Send message and add reactions for equippable/droppable items
        message = await ctx.send(embed=embed)

        # Add reactions for equippable and droppable items
        for slot in inventory.slots.values():
            if slot.item.type.value in ['weapon', 'helmet', 'armor', 'pants', 'boots', 'ring', 'amulet']:
                await message.add_reaction(EQUIP_EMOJI)
            await message.add_reaction(DROP_EMOJI)

        # Store the inventory message for reaction handling
        self.pending_actions[message.id] = {
            'type': 'inventory',
            'owner_id': ctx.author.id,
            'inventory': inventory
        }

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle inventory/equipment reactions"""
        # Ignore bot's own reactions
        if user.bot:
            return

        message = reaction.message
        if message.id not in self.pending_actions:
            return

        action_data = self.pending_actions[message.id]
        if user.id != action_data['owner_id']:
            return

        if action_data['type'] == 'inventory':
            await self.handle_inventory_reaction(reaction, user, action_data)
        elif action_data['type'] == 'equipment':
            await self.handle_equipment_reaction(reaction, user, action_data)

        # Remove the user's reaction
        await reaction.remove(user)

    async def handle_inventory_reaction(self, reaction, user, action_data):
        """Handle reactions on inventory messages"""
        inventory = action_data['inventory']
        emoji = str(reaction.emoji)

        # Find the item that was reacted to
        target_item = None
        for slot in inventory.slots.values():
            if any(line.endswith(slot.item.name) for line in reaction.message.embeds[0].fields[0].value.split('\n')):
                target_item = slot.item
                break

        if not target_item:
            return

        if emoji == EQUIP_EMOJI and target_item.type.value in ['weapon', 'helmet', 'armor', 'pants', 'boots', 'ring', 'amulet']:
            # Get current equipment
            equipment = await self.inventory_manager.get_equipment(user.id)

            # Handle rings specially
            if target_item.type.value == 'ring':
                if not equipment.ring1:
                    equipment.ring1 = target_item
                elif not equipment.ring2:
                    equipment.ring2 = target_item
                else:
                    # Replace ring1 and move it to inventory
                    if equipment.ring1:
                        inventory.add_item(equipment.ring1, 1)
                    equipment.ring1 = target_item

            else:
                # Handle other equipment slots
                slot_name = target_item.type.value
                current_item = getattr(equipment, slot_name)
                
                # If there's an item already equipped, move it to inventory
                if current_item:
                    inventory.add_item(current_item, 1)
                
                # Equip new item
                setattr(equipment, slot_name, target_item)

            # Remove equipped item from inventory
            inventory.remove_item(target_item.id, 1)

            # Save changes
            await self.inventory_manager.save_equipment(user.id, equipment)
            await self.inventory_manager.save_inventory(inventory)

            # Update message
            await self.update_inventory_message(reaction.message, user.id)

        elif emoji == DROP_EMOJI:
            # Remove item from inventory
            inventory.remove_item(target_item.id, 1)
            await self.inventory_manager.save_inventory(inventory)

            # Update message
            await self.update_inventory_message(reaction.message, user.id)

    async def handle_equipment_reaction(self, reaction, user, action_data):
        """Handle reactions on equipment messages"""
        equipment = action_data['equipment']
        emoji = str(reaction.emoji)

        # Find which slot was reacted to
        slot_name = None
        for name, slot_emoji in EQUIPMENT_SLOT_EMOJIS.items():
            if emoji == slot_emoji:
                slot_name = name
                break

        if not slot_name:
            return

        # Get the item from the slot
        item = getattr(equipment, slot_name)
        if not item:
            return

        # Move item to inventory
        inventory = await self.inventory_manager.get_inventory(user.id)
        if inventory:
            inventory.add_item(item, 1)
            setattr(equipment, slot_name, None)

            # Save changes
            await self.inventory_manager.save_equipment(user.id, equipment)
            await self.inventory_manager.save_inventory(inventory)

            # Update message
            await self.update_equipment_message(reaction.message, user.id)

    async def update_inventory_message(self, message, user_id):
        """Update inventory message after changes"""
        inventory = await self.inventory_manager.get_inventory(user_id)
        if not inventory:
            return

        # Create updated embed
        embed = discord.Embed(
            title=f"🎒 {message.guild.get_member(user_id).name}'s Inventory ({len(inventory.slots)}/{inventory.max_slots} slots)",
            color=discord.Color.blue()
        )

        # Rebuild the embed fields
        items_by_type = {}
        for slot in inventory.slots.values():
            item_type = slot.item.type.value
            if item_type not in items_by_type:
                items_by_type[item_type] = []
            items_by_type[item_type].append(slot)

        for item_type in ItemType:
            if item_type.value not in items_by_type:
                continue

            items_text = []
            for slot in sorted(items_by_type[item_type.value], key=lambda x: x.item.name):
                rarity_prefix = "⚪" if slot.item.rarity == ItemRarity.COMMON else \
                              "🟢" if slot.item.rarity == ItemRarity.UNCOMMON else \
                              "🔵" if slot.item.rarity == ItemRarity.RARE else \
                              "🟣" if slot.item.rarity == ItemRarity.EPIC else "🟡"
                
                count_text = f" x{slot.count}" if slot.count > 1 else ""
                level_text = f" (Lvl {slot.item.level_requirement})" if slot.item.level_requirement > 1 else ""
                items_text.append(f"{rarity_prefix} {slot.item.name}{count_text}{level_text}")

            if items_text:
                embed.add_field(
                    name=f"📦 {item_type.value.title()}",
                    value="\n".join(items_text),
                    inline=False
                )

        await message.edit(embed=embed)

    async def update_equipment_message(self, message, user_id):
        """Update equipment message after changes"""
        equipment = await self.inventory_manager.get_equipment(user_id)
        if not equipment:
            return

        embed = discord.Embed(
            title=f"⚔️ {message.guild.get_member(user_id).name}'s Equipment",
            color=discord.Color.gold()
        )

        for slot_name, emoji in EQUIPMENT_SLOT_EMOJIS.items():
            item = getattr(equipment, slot_name)
            if item:
                rarity_prefix = "⚪" if item.rarity == ItemRarity.COMMON else \
                              "🟢" if item.rarity == ItemRarity.UNCOMMON else \
                              "🔵" if item.rarity == ItemRarity.RARE else \
                              "🟣" if item.rarity == ItemRarity.EPIC else "🟡"
                value = f"{rarity_prefix} {item.name} (Lvl {item.level_requirement})"
            else:
                value = "Empty"
            
            embed.add_field(
                name=f"{emoji} {slot_name.title()}",
                value=value,
                inline=True
            )

        stats = equipment.get_total_stats()
        stats_text = []
        for stat, value in stats.items():
            if value != 0:
                if stat in ['crit_chance', 'flee_chance']:
                    stats_text.append(f"{stat.replace('_', ' ').title()}: +{value}%")
                else:
                    stats_text.append(f"{stat.replace('_', ' ').title()}: +{value}")

        if stats_text:
            embed.add_field(
                name="📊 Total Stats",
                value="\n".join(stats_text),
                inline=False
            )

        await message.edit(embed=embed)

    @commands.command(name='use')
    async def use_item(self, ctx, *, item_name: str):
        """Use a consumable item"""
        inventory = await self.inventory_manager.get_inventory(ctx.author.id)
        if not inventory:
            await ctx.send("You don't have a character yet! Use `!wb start` to create one.")
            return

        # Find item in inventory
        item = None
        for slot in inventory.slots.values():
            if slot.item.name.lower() == item_name.lower():
                item = slot.item
                break

        if not item:
            await ctx.send(f"You don't have an item called '{item_name}'.")
            return

        if item.type != ItemType.CONSUMABLE:
            await ctx.send(f"You can't use {item.name}. Only consumable items can be used.")
            return

        # Apply item effects
        async with self.bot.db.execute(
            'SELECT health, max_health, mana, max_mana FROM players WHERE id = ?',
            (ctx.author.id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                await ctx.send("Error: Could not find player data.")
                return

            health, max_health, mana, max_mana = row
            updates = []
            effects_text = []

            for effect in item.effects:
                if effect.type == 'heal':
                    new_health = min(max_health, health + effect.value)
                    healing_done = new_health - health
                    health = new_health
                    updates.append(('health', health))
                    effects_text.append(f"Restored {healing_done} health")

                elif effect.type == 'mana':
                    new_mana = min(max_mana, mana + effect.value)
                    mana_restored = new_mana - mana
                    mana = new_mana
                    updates.append(('mana', mana))
                    effects_text.append(f"Restored {mana_restored} mana")

            if updates:
                # Update player stats
                update_query = 'UPDATE players SET ' + ', '.join(f'{field} = ?' for field, _ in updates)
                update_values = [value for _, value in updates]
                update_values.append(ctx.author.id)
                
                await self.bot.db.execute(
                    update_query + ' WHERE id = ?',
                    update_values
                )

                # Remove one item from inventory
                inventory.remove_item(item.id, 1)
                await self.inventory_manager.save_inventory(inventory)

                # Send success message
                embed = discord.Embed(
                    title=f"Used {item.name}",
                    description="\n".join(effects_text),
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Current Stats",
                    value=f"Health: {health}/{max_health}\nMana: {mana}/{max_mana}"
                )
                await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(InventoryCommands(bot))