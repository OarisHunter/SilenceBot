# bot.py
import asyncio
import datetime
import os

import discord
from dotenv import load_dotenv
from discord.ext import commands
from configparser import ConfigParser

# Load Environment Variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

# Set current purge time
purge_time = datetime.datetime.now()

# Create Bot
config_object = ConfigParser()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='<', intents=intents)
guild = None
guild_owner = None

# ---------------- Set Vars From Config -------------------
config_object.read("config.ini")
# Get Config Headers
bot_info = config_object["BOT_INFO"]
user_info = config_object["USER_INFO"]

# BOT_INFO header values
game = bot_info["game"]
message_lockout_time = int(bot_info["message_lockout_time"])
admin_txt_channel_id = int(bot_info["admin_txt_channel_id"])
silenced_voice_channel_id = int(bot_info["silenced_voice_channel_id"])
lock_mode = bot_info["auto_lock"]

# USER_INFO header values
silencedId = user_info["silencedId"].split(',')  # Creates a list of silenced IDs
silencedNick = user_info["silencedNick"]


@bot.event
async def on_ready():
    try:
        # Get guild from bot.guilds
        for g in bot.guilds:
            if g.name == GUILD:
                global guild
                global guild_owner
                guild = g
                guild_owner = guild.owner
                break

        # Convert silenceId string list from config to int list
        for i in range(len(silencedId)):
            silencedId[i] = int(silencedId[i])

        # Debug Display bot connected
        print(f"Silence Bot Ready:\n"
              f"    {bot.user.name} has connected to {guild.owner.name}'s |{guild.name}| at {purge_time}\n"
              f"    Autolock: {lock_mode}")

        # Change bot presence
        await bot.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=game))

    except discord.DiscordException:
        print(f'on_ready event failed')


# ------------------ Commands --------------------- #


@bot.command(name="verify", help='Adds a User to the Silenced List')
async def user_verify(ctx, user_id: int):
    if ctx.author == guild_owner:
        reply = await ctx.channel.send(
            f"Verified {ctx.guild.get_member(user_id).name}")

        await verify(ctx.guild.get_member(user_id))

        await ctx.message.delete(delay=3)
        await reply.delete(delay=3)
    else:
        reply = await ctx.channel.send(
            f"**Verify:** Commands can only be sent by the Server Owner.")
        await reply.delete(delay=3)


@bot.command(name="deny", help='Removes a User from the Silenced List')
async def user_deny(ctx, user_id: int):
    if ctx.author == ctx.guild.owner:
        reply = await ctx.channel.send(
            f"Added {ctx.guild.get_member(user_id).name} to the denied list")

        await deny(ctx.guild.get_member(user_id))

        await ctx.message.delete(delay=3)
        await reply.delete(delay=3)
    else:
        reply = await ctx.channel.send(
            f"**Verify:** Commands can only be sent by the Server Owner.")
        await reply.delete(delay=3)


@bot.command(name='purge', help='Purges a certain number of messages in the current channel')
async def manual_purge(ctx, amount: int):
    if ctx.author == ctx.guild.owner:
        try:
            deleted = await ctx.channel.purge(limit=amount + 1)
        except discord.HTTPException:
            print(f'Purging the messages failed.')
            deleted = []

        reply = await ctx.channel.send(
            f"**Purge:** {len(deleted) - 1} messages purged from {ctx.channel.name}.")
        await reply.delete(delay=3)
    else:
        reply = await ctx.channel.send(
            f"**Purge:** Commands can only be sent by the Server Owner.")
        await reply.delete(delay=3)


# ------------------ Events --------------------- #


@bot.event
async def on_voice_state_update(member, before, after):
    if after.channel is not None:
        print(f"User Connected to Voice Channel {after.channel.name}")
        if member.id in silencedId and after.channel.id != silenced_voice_channel_id:
            try:
                await member.move_to(member.guild.get_channel(silenced_voice_channel_id), reason="Automated Move")
            except discord.HTTPException:
                print(f'Failed to move member')
    else:
        print(f"User Disconnected from Voice Channel {before.channel.name}")


@bot.event
async def on_message(ctx):
    # Ignore bot messages
    if ctx.author == bot.user:
        return

    if ctx.author.id in silencedId:
        # Get current purge time
        global purge_time

        try:
            # Purge all messages from users in silenced list starting from the current purge time
            await ctx.channel.purge(limit=100, check=should_purge_auto, oldest_first=False, bulk=True,
                                    after=purge_time)
        except discord.HTTPException:
            print(f'Purging the messages failed.')

        # Update purge time
        purge_time = datetime.datetime.now()

        # Lock users on silenced list from sending additional messages
        if lock_mode == 1:
            await message_permissions_autolock(ctx.channel, ctx.author)
        else:
            await message_permissions_lock(ctx.author)

            # Notify Server Owner if permissions lock was bypassed
            await ctx.channel.send(f"{guild_owner.mention}\n"
                                   f"User {ctx.author}'s permission settings were bypassed")

    await bot.process_commands(ctx)


@bot.event
async def on_member_update(before, after):
    if after.id in silencedId and after in guild.members:
        await deny(after)


@bot.event
async def on_user_update(before, after):
    if after.id in silencedId and after in guild.members:
        await deny(after)


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    emoji = reaction.emoji
    admin_channel = user.guild.get_channel(admin_txt_channel_id)
    user_ID = welcome_get_id(reaction.message)

    if user == guild_owner:
        try:
            if emoji == '✅':
                # Reply to reaction
                reply = await admin_channel.send(f"User {reaction.message.guild.get_member(user_ID).name} Verified.")

                # verify user
                await verify(reaction.message.guild.get_member(user_ID))

                # Delete replay and original message
                await reply.delete(delay=3)
                await reaction.message.delete(delay=3)
            elif emoji == '❌':
                # Reply to reaction
                reply = await admin_channel.send(f"User {reaction.message.guild.get_member(user_ID).name} Denied.")

                # deny user
                await deny(reaction.message.guild.get_member(user_ID))

                # Delete replay and original message
                await reply.delete(delay=3)
                await reaction.message.delete(delay=3)
        except discord.DiscordException:
            print(f'Could not manage added reaction')
    else:
        # Reply to reaction
        reply = await admin_channel.send(f"Only the Server Owner can verify new Members")

        # Delete replay and original message
        await reply.delete(delay=3)


@bot.event
async def on_member_join(member):
    try:
        # Get admin channel
        admin_channel = member.guild.get_channel(admin_txt_channel_id)

        # Deny Member
        await deny(member)

        # Send welcome message
        welcome_message = await admin_channel.send(
            f"**----- Automated Silence -----**\n\nUser {member.name} joined the Server and was added to the Silenced"
            f" list\n\nUser ID: {member.id} \n\nOwner must select an option to validate new Member")

        # Add Reaction to Welcome Message
        reactions = ['✅', '❌']
        for emoji in reactions:
            await welcome_message.add_reaction(emoji)

    except discord.DiscordException:
        print("Failed to print welcome message.")

    try:
        await member.create_dm()
        await member.dm_channel.send(
            f"Hello and Welcome {member.name}.\n\nAccess to text and voice channels have been "
            f"restricted due to past new Members.\n\n"
            f"Your account is awaiting manual verification from the server Owner. "
            f"If you are here temporarily, ignore this message.")
    except discord.DiscordException:
        print("Failed to DM Member.")


# ------------------ Async Functions --------------------- #


# Verifies Member
async def verify(member):
    silenced_list_del(member)

    await message_permissions_unlock(member)
    await voice_permissions_unlock(member)

    await clear_nick(member)


# Denies Member access to most server functions
async def deny(member):
    # Remove Member from silenced List
    silenced_list_add(member)

    # Lock member from sending messages
    if lock_mode == 0:
        await message_permissions_lock(member)
    await voice_permissions_lock(member)

    # Set nickname
    await set_nick(member)


# Changes the members nickname to the config defined value
async def set_nick(member):
    try:
        if member.display_name != silencedNick:
            await member.edit(nick=silencedNick)
    except discord.HTTPException:
        print(f'Nickname change failed.')


# Changes the members nickname to the config defined value
async def clear_nick(member):
    try:
        await member.edit(nick=None)
    except discord.HTTPException:
        print(f'Nickname clear failed.')


# on_message helper function, locks a member from sending messages in a channel, then unlocks them later
async def message_permissions_autolock(channel, member):
    try:
        # Change member permissions to not send messages
        overwrite = discord.PermissionOverwrite()
        overwrite.send_messages = False
        try:
            await channel.set_permissions(member, overwrite=overwrite, reason="Silenced Member Message Timeout Start")
        except discord.NotFound:
            print(f'The member being edited is not part of the guild.')

        # message lockout time
        await asyncio.sleep(message_lockout_time)

        try:
            await channel.set_permissions(member, overwrite=None, reason="Silenced Member Message Timeout End")
        except discord.NotFound:
            print(f'The member being edited is not part of the guild.')
        # Change member permissions to send messages again

    except discord.DiscordException:
        print(f'Failed to autolock member permissions')


# helper function, locks a member from sending messages in all channels
async def message_permissions_lock(member):
    try:
        # Change member permissions to not send messages
        overwrite = discord.PermissionOverwrite()
        overwrite.send_messages = False

        for channel in member.guild.text_channels:
            try:
                await channel.set_permissions(member, overwrite=overwrite, reason="Locked User from Text Channels")
            except discord.NotFound:
                print(f'The member being edited is not part of the guild.')
    except discord.DiscordException:
        print(f'Failed to lock member permissions')


# helper function, unlocks a member from sending messages in all channels
async def message_permissions_unlock(member):
    try:
        # Change member permissions to send messages again
        for channel in member.guild.text_channels:
            try:
                await channel.set_permissions(member, overwrite=None, reason="Unlocked User from Text Channels")
            except discord.NotFound:
                print(f'The member being edited is not part of the guild.')

    except discord.DiscordException:
        print(f'Failed to unlock member permissions')


# helper function, locks a member from sending messages in all channels
async def voice_permissions_lock(member):
    try:
        # Change member permissions to not send messages
        overwrite = discord.PermissionOverwrite()
        overwrite.view_channel = False

        for channel in member.guild.voice_channels:
            if channel.id != silenced_voice_channel_id:
                try:
                    await channel.set_permissions(member, overwrite=overwrite, reason="Locked User from Voice Channels")
                except discord.NotFound:
                    print(f'The member being edited is not part of the guild.')
    except discord.DiscordException:
        print(f'Failed to lock member permissions')


# helper function, unlocks a member from sending messages in all channels
async def voice_permissions_unlock(member):
    try:
        # Change member permissions to send messages again
        for channel in member.guild.voice_channels:
            try:
                await channel.set_permissions(member, overwrite=None, reason="Unlocked User from Voice Channels")
            except discord.NotFound:
                print(f'The member being edited is not part of the guild.')

    except discord.DiscordException:
        print(f'Failed to unlock member permissions')


# ------------------ Functions --------------------- #


# on_message helper function, determines if a message should be purged using the silenced list
def should_purge_auto(message):
    if message.author.id in silencedId:
        return True
    else:
        return False


# Adds a member to the silenced list
def silenced_list_add(member):
    # Add new member to silencedId if ID is not already listed
    if member.id in silencedId:
        return
    silencedId.append(member.id)

    # Convert silenceId int list to string list
    new_list = silencedId.copy()
    for i in range(len(new_list)):
        new_list[i] = str(new_list[i])
    # Update silencedId
    user_info["silencedId"] = ",".join(new_list)

    # Write to config.ini
    with open('config.ini', 'w') as conf:
        config_object.write(conf)


# Removes a member from the silenced list
def silenced_list_del(member):
    # Convert silenceId int list to string list
    try:
        silencedId.remove(member.id)
    except ValueError:
        print("Value not found")

    # Convert silenceId int list to string list
    new_list = silencedId.copy()
    for i in range(len(new_list)):
        new_list[i] = str(new_list[i])
    # Update silencedId
    user_info["silencedId"] = ",".join(new_list)

    # Write to config.ini
    with open('config.ini', 'w') as conf:
        config_object.write(conf)


# Get ID out of welcome/verification message
def welcome_get_id(message):
    index = message.clean_content.find("User ID: ")
    content = message.clean_content[index:]
    return int(content.split(' ')[2])


# --------------------------------------------------- #

bot.run(TOKEN)
