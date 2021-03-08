# bot_OLD.py
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

# Open Config File
config_object = ConfigParser()
config_object.read("config.ini")

# Create Bot
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='<', intents=intents)

# Get Config Headers
bot_info = config_object["BOT_INFO"]
user_info = config_object["USER_INFO"]

# BOT_INFO header values
game = bot_info["game"]
message_lockout_time = int(bot_info["message_lockout_time"])
admin_txt_channel_id = int(bot_info["admin_txt_channel_id"])
silenced_voice_channel_id = int(bot_info["silenced_voice_channel_id"])

# USER_INFO header values
silencedId = user_info["silencedId"].split(',')     # Creates a list of silenced IDs
silencedNick = user_info["silencedNick"]

# Set current purge time
purge_time = datetime.datetime.now()


@bot.event
async def on_ready():
    try:
        # Get Guild for message display
        for guild in bot.guilds:
            if guild.name == GUILD:
                break

        # Convert silenceId string list from config to int list
        for i in range(len(silencedId)):
            silencedId[i] = int(silencedId[i])

        # Debug Display bot connected
        print(f"{bot.user.name} has connected to {guild.owner.name}'s |{guild.name}| at {purge_time}")

        # Change bot presence
        await bot.change_presence(activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=game))
    except discord.DiscordException:
        print(f'on_ready event failed')


# ------------------ Commands --------------------- #


@bot.command(name="verify", help='Adds a User to the Silenced List')
async def add_silenced_user(ctx, user_id: int):
    try:
        if ctx.author == ctx.guild.owner:
            await verify(ctx.guild.get_member(user_id))

            reply = await ctx.channel.send(
                f"Verified {ctx.guild.get_member(user_id).name}")
            await ctx.message.delete(delay=3)
            await reply.delete(delay=3)
    except discord.DiscordException:
        print(f'Couldnt add silenced user')


@bot.command(name="deny", help='Removes a User from the Silenced List')
async def delete_silenced_user(ctx, user_id: int):
    try:
        if ctx.author == ctx.guild.owner:
            await deny(ctx.guild.get_member(user_id))

            reply = await ctx.channel.send(
                f"Added {ctx.guild.get_member(user_id).name} to the denied list")
            await ctx.message.delete(delay=3)
            await reply.delete(delay=3)
    except discord.DiscordException:
        print(f'Couldnt delete silenced user')


@bot.command(name='purge', help='Purges a certain number of messages in the current channel')
async def manual_purge(ctx, amount: int):
    try:
        if ctx.author == ctx.guild.owner:
            try:
                deleted = await ctx.channel.purge(limit=amount + 1)
                reply = await ctx.channel.send(
                    f"**Purge:** {len(deleted) - 1} messages purged from {ctx.channel.name}.")
                await reply.delete(delay=3)
            except discord.DiscordException:
                print(f'Couldnt purge messages')
    except discord.DiscordException:
        print(f'Manual purge failed')


@bot.command(name='purgefrom', help='Purges all messages after the given message ID')
async def manual_purge_from(ctx, message_id: int):
    try:
        if ctx.author == ctx.guild.owner:
            try:
                start_message = await ctx.channel.fetch_message(message_id)
                deleted = await ctx.channel.purge(after=start_message.created_at)
                await start_message.delete()
                reply = await ctx.channel.send(
                    f"**Purge:** {len(deleted)} messages purged from {ctx.channel.name}.")
                await reply.delete(delay=3)
            except discord.NotFound:
                print(f'Couldnt purge from messages')
    except discord.DiscordException:
        print(f'Manual purge from failed')


@bot.command(name='purgeuser', help='Purges up to 100 messages from the given user')
async def manual_purge_user(ctx, user_id: int, amount: int):
    try:
        if ctx.author == ctx.guild.owner:
            to_delete = []

            if amount >= 99:
                amount = 100

            try:
                async for message in ctx.channel.history(limit=amount+1):
                    if message.author.id == user_id:
                        to_delete.append(message)
            except discord.DiscordException:
                print(f'Couldnt get message list')

            try:
                if len(to_delete) > 0:
                    deleted = await ctx.channel.delete_messages(to_delete)
                    reply = await ctx.channel.send(
                        f"**Purge:** {amount} messages purged from {ctx.channel.name}.")
                    await reply.delete(delay=3)
            except discord.DiscordException:
                print(f'Couldnt delete user messages')

    except discord.DiscordException:
        print(f'Manual purge user failed')


# ------------------ Events --------------------- #


@bot.event
async def on_voice_state_update(member, before, after):
    try:
        for silenced in silencedId:
            if after.channel is not None:
                if member.id == silenced and after.channel.id != silenced_voice_channel_id:
                    try:
                        await member.move_to(member.guild.get_channel(silenced_voice_channel_id), reason="Automated Move")
                    except discord.DiscordException:
                        print(f'Failed to move member')
    except discord.DiscordException:
        print(f'Automatic Member Move failed')


@bot.event
async def on_message(ctx):
    try:
        for memberId in silencedId:
            if ctx.author.id == memberId:
                try:
                    # Get current purge time
                    global purge_time

                    # purge all messages from users in silenced list starting from the current purge time
                    deleted = await ctx.channel.purge(limit=100, check=should_purge_auto, oldest_first=False, bulk=True,
                                                      after=purge_time)

                    # Update purge time
                    purge_time = datetime.datetime.now()

                    # Deny User
                    await deny(ctx.author)

                except discord.DiscordException:
                    print(f'Couldnt purge messages')

                # Lock users on silenced list from sending additional messages
                # await message_permissions_autolock(ctx.channel, ctx.author)

    except discord.DiscordException:
        print(f'on_message check failed')

    # Fix overwriting on_message breaking commands
    try:
        await bot.process_commands(ctx)
    except discord.DiscordException:
        print(f'Couldnt pass to process commands')


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    emoji = reaction.emoji
    admin_channel = user.guild.get_channel(admin_txt_channel_id)
    user_ID = welcome_get_id(reaction.message)

    if user == admin_channel.guild.owner:
        try:
            if emoji == '✅':
                # verify user
                await verify(reaction.message.guild.get_member(user_ID))

                # Reply to reaction
                reply = await admin_channel.send(f"User {reaction.message.guild.get_member(user_ID).name} Verified.")

                # Delete replay and original message
                await reply.delete(delay=3)
                await reaction.message.delete(delay=3)
            elif emoji == '❌':
                # deny user
                await verify(reaction.message.guild.get_member(user_ID))

                # Reply to reaction
                reply = await admin_channel.send(f"User {reaction.message.guild.get_member(user_ID).name} Denied.")

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
async def on_member_update(before, after):
    for id in silencedId:
        if after.id == id:
            await deny(after)


@bot.event
async def on_user_update(before, after):
    for id in silencedId:
        if after.id == id:
            await deny(after)


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


# on_message helper function, locks a member from sending messages in a channel, then unlocks them later
async def message_permissions_autolock(channel, member):
    try:
        # Change member permissions to not send messages
        overwrite = discord.PermissionOverwrite()
        overwrite.send_messages = False
        await channel.set_permissions(member, overwrite=overwrite, reason="Silenced Member Message Timeout Start")

        # message lockout time
        await asyncio.sleep(message_lockout_time)

        # Change member permissions to send messages again
        await channel.set_permissions(member, overwrite=None, reason="Silenced Member Message Timeout End")
    except discord.DiscordException:
        print(f'Failed to edit member permissions')


# helper function, locks a member from sending messages in all channels
async def message_permissions_lock(member):
    try:
        # Change member permissions to not send messages
        overwrite = discord.PermissionOverwrite()
        overwrite.send_messages = False

        for channel in member.guild.text_channels:
            await channel.set_permissions(member, overwrite=overwrite, reason="Silenced Member Message Timeout Start")
    except discord.DiscordException:
        print(f'Failed to edit member permissions')


# helper function, unlocks a member from sending messages in all channels
async def message_permissions_unlock(member):
    try:
        # Change member permissions to send messages again
        for channel in member.guild.text_channels:
            await channel.set_permissions(member, overwrite=None, reason="Silenced Member Message Timeout End")

    except discord.DiscordException:
        print(f'Failed to edit member permissions')


# Changes the members nickname to the config defined value
async def set_nick(member):
    try:
        await member.edit(nick=silencedNick)
    except discord.DiscordException:
        print(f'Nickname change failed.')


# Changes the members nickname to the config defined value
async def clear_nick(member):
    try:
        await member.edit(nick=None)
    except discord.DiscordException:
        print(f'Nickname clear failed.')


# Verifies Member
async def verify(member):
    # Remove Member from silenced List
    silenced_list_del(member)

    # Unlock member from sending messages
    await message_permissions_unlock(member)

    # Clear nickname
    await clear_nick(member)


# Denies Member access to most server functions
async def deny(member):
    # Remove Member from silenced List
    silenced_list_add(member)

    # Lock member from sending messages
    await message_permissions_lock(member)

    # Set nickname
    await set_nick(member)


# ------------------ Functions --------------------- #


# on_message helper function, determines if a message should be purged using the silenced list
def should_purge_auto(message):
    for memberId in silencedId:
        if message.author.id == memberId:
            return True
    return False


# Get ID out of welcome/verification message
def welcome_get_id(message):
    index = message.clean_content.find("User ID: ")
    content = message.clean_content[index:]
    return int(content.split(' ')[2])


# Adds a member to the silenced list
def silenced_list_add(member):
    # Add new member to silencedId if ID is not already listed
    for i in silencedId:
        if i == member.id:
            return
    silencedId.append(member.id)

    # Convert silenceId int list to string list
    new_list = silencedId.copy()
    for i in range(len(new_list)):
        new_list[i] = str(new_list[i])
    new_silencedId = ",".join(new_list)

    # Update silencedId
    user_info["silencedId"] = new_silencedId

    # Write to config.ini
    with open('config.ini', 'w') as conf:
        config_object.write(conf)


# Removes a member from the silenced list
def silenced_list_del(member):
    # Convert silenceId int list to string list
    try:
        silencedId.remove(member.id)

        # Convert silenceId int list to string list
        new_list = silencedId.copy()
        for i in range(len(new_list)):
            new_list[i] = str(new_list[i])
        new_silencedId = ",".join(new_list)

        # Update silencedId
        user_info["silencedId"] = new_silencedId

        # Write to config.ini
        with open('config.ini', 'w') as conf:
            config_object.write(conf)

    except ValueError:
        print("Value not found")


# --------------------------------------------------- #

bot.run(TOKEN)
