import asyncio
import datetime
import json

from discord import Message, Embed, Guild, TextChannel
import discord
from discord.ext import tasks
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.chat_formatting import humanize_number
from redbot.core import commands, Config, bot as RedBot, errors, i18n
from discord.errors import NotFound as DiscordNotFoundError
from vk.exceptions import VkException, VkAPIError, VkAuthError

from redbot.core.i18n import Translator, cog_i18n

from .log import log

import vk

_ = Translator("VKHook", __file__)

VK_VERSION = "5.131"
WALLS_KEY = "VKHookWalls"


def get_post_url(wall_id: int, post_id: int):
    return "https://vk.com/wall"+str(wall_id)+"_"+str(post_id)


def get_good_photo(post: dict) -> str:
    images = {'x': '', 'm': '', 's': ''}
    image_priorities = ['x', 'm', 's']
    is_found = False
    if "attachments" in post and len(post['attachments']) > 0:
        for attachment in post['attachments']:
            if attachment['type'] == 'photo':
                for size in attachment['photo']['sizes']:
                    if size['type'] in images.keys():
                        is_found = True
                        images[size['type']] = size['url']
                if is_found:
                    break
    if is_found:
        for priority in image_priorities:
            if images[priority] != '':
                return images[priority]


def find_last_post(posts: list) -> dict:
    if "is_pinned" in posts[0] and posts[0]['is_pinned']:
        if posts[0]['date'] < posts[1]['date']:
            return posts[1]
    return posts[0]


def find_posts_after(posts: list, date: int) -> list:
    posts = sorted(posts, key=lambda post: post['date'], reverse=True)
    result = []
    for post in posts:
        if post['date'] > date:
            result.append(post)
            continue
        break
    result.reverse()
    return result


@cog_i18n(_)
class VKHook(commands.Cog):
    """VKHook related commands"""

    bot: RedBot

    def __init__(self, bot: RedBot, *args, **kwargs):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=13371448228)

        default_wall = {
            'channels': [],
            'last_date': -1
        }

        self.config.init_custom(WALLS_KEY, 1)
        self.config.register_custom(WALLS_KEY, **default_wall)

        self.update_walls_job.start()

        super().__init__(*args, **kwargs)

    def cog_unload(self):
        self.update_walls_job.cancel()
        self.session.detach()

    @tasks.loop(minutes=3.0)
    async def update_walls_job(self):
        walls = await self.config.custom(WALLS_KEY).all()

        service_key = await self.get_api_key(ctx=None)
        if service_key is None:
            return

        session = vk.Session()
        session.access_token = service_key

        api = vk.API(session=session)

        for wall_id, data in walls.items():

            if len(data['channels']) == 0:
                continue
            wall = {}
            try:
                wall = api.wall.get(owner_id=wall_id, filter="owner", v=VK_VERSION)
            except VkAuthError as e:
                log.exception(e)
                continue
            except VkAPIError as e:
                log.exception(e)
                await self.clear_wall(int(wall_id))
                continue
            except VkException as e:
                log.exception(e)
                continue

            account = {}

            try:
                account = await self.get_account(int(wall_id), service_key)
            except VkAuthError as e:
                log.exception(e)
                continue
            except VkAPIError as e:
                log.exception(e)
                await self.clear_wall(int(wall_id))
                continue
            except VkException as e:
                log.exception(e)
                continue

            posts_to_send = [find_last_post(wall['items'])] \
                if data['last_date'] == -1 else \
                find_posts_after(wall['items'], data['last_date'])

            if len(posts_to_send) == 0:
                continue

            await self.config.custom(WALLS_KEY, wall_id).last_date.set(posts_to_send[-1]['date'])

            for channel_info in data['channels']:
                guild = -1
                try:
                    guild = await self.bot.fetch_guild(channel_info['guild_id'])
                except discord.errors.Forbidden as e:
                    await self.clear_channel(
                        channel_id=channel_info['channel_id'],
                        guild_id=channel_info['guild_id']
                    )
                    log.exception(e)
                    continue
                except discord.errors.HTTPException as e:
                    log.exception(e)
                    continue
                if guild == -1:
                    continue

                channel = self.bot.get_channel(channel_info['channel_id'])

                if channel is None:
                    continue

                try:
                    await self.send_posts_from_wall(
                        posts=posts_to_send,
                        account=account,
                        channel=channel,
                        service_key=service_key
                    )
                except discord.errors.Forbidden as e:
                    log.exception(e)
                    continue

    @update_walls_job.before_loop
    async def before_update_walls_job(self):
        await self.bot.wait_until_red_ready()

    async def get_api_key(self, ctx: commands.Context = None):
        api_keys = await self.bot.get_shared_api_tokens("vk_hook")
        if not api_keys and ctx is not None:
            await ctx.send(_("Error! VK ``service_key`` is not provided! Set it by ``[p]set api "
                             "vk_hook service_key,[YOUR SERVICE KEY]``."))
        return api_keys.get("service_key")

    @commands.group(alias=["vkh"])
    async def vkhook(self, ctx: commands.Context):
        """VKHook related commands"""

        pass

    @vkhook.command(alias=['sub'])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_webhooks=True)
    async def subscribe(self, ctx: commands.Context, channel: discord.TextChannel, wall_id: int):
        """Subscribes the channel to VK wall updates

        Example: ``[p]vkhook subscribe <channel> <wall_id>``"""

        channel_obj = {
            'channel_id': channel.id,
            'guild_id': ctx.guild.id
        }
        current_channels = await self.config.custom(WALLS_KEY, str(wall_id)).channels()

        if len([item for item in current_channels
                if item['channel_id'] == channel.id and
                   item['guild_id'] == channel.guild.id]) > 0: # Fuck LINQ
            await ctx.send(_("This channel is already subscribed to updates on this wall. Nothing to do."))
            return

        service_key = await self.get_api_key(ctx=ctx)
        if service_key is None:
            return

        session = vk.Session()
        session.access_token = service_key

        api = vk.API(session=session)

        wall = {}

        try:
            wall = api.wall.get(owner_id=wall_id, filter="owner", v=VK_VERSION)
        except VkAuthError:
            await ctx.send(_("An authorisation error occurred when trying to retrieve the user's information.\n"
                             "Set new by ``[p]set api vk_hook service_key,[YOUR SERVICE KEY]``."))
            return
        except VkAPIError as e:
            await ctx.send(_("An API error occurred when trying to retrieve user's information. Here is the "
                             "information about this error:")+"\n\n```"+
                           _("Error code: {error_code}\nError message: \"{error_msg}\"")
                           .format(error_code=e.code, error_msg=e.message)+
                           "```")
            return
        except VkException:
            await ctx.send(_("An unexpected exception was raised when trying to retrieve user wall information. Try "
                             "again later."))
            return

        if "count" not in wall and int(wall['count']) < 1:
            await ctx.send(_("You must give a wall with at least one entry! Post something and try again."))
            return

        account = {}

        try:
            account = await self.get_account(wall_id, service_key)
        except VkAuthError as e:
            await ctx.send(
                _("An authorization error occurred when trying to retrieve the user's information.\n"
                  "Set new by ``[p]set api vk_hook service_key,[YOUR SERVICE KEY]``."))
            log.exception(e)
            return
        except VkAPIError as e:
            await ctx.send(_("An API error occurred when trying to retrieve user's information. Here is the "
                             "information about this error:") + "\n\n```" +
                           _("Error code: {error_code}\nError message: \"{error_msg}\"")
                           .format(error_code=e.code, error_msg=e.message) + "```")
            log.exception(e)
            return
        except VkException as e:
            await ctx.send(
                _("An unexpected exception was raised when trying to retrieve user wall information. Try "
                  "again later."))
            log.exception(e)
            return

        post = find_last_post(wall['items'])

        try:
            await self.send_posts_from_wall(posts=[post], account=account, channel=channel, service_key=service_key)
        except VkAuthError as e:
            await ctx.send(
                _("An authorization error occurred when trying to retrieve the user's information.\n"
                  "Set new by ``[p]set api vk_hook service_key,[YOUR SERVICE KEY]``."))
            log.exception(e)
            return
        except VkAPIError as e:
            await ctx.send(_("An API error occurred when trying to retrieve user's information. Here is the "
                             "information about this error:") + "\n\n```" +
                           _("Error code: {error_code}\nError message: \"{error_msg}\"")
                           .format(error_code=e.code, error_msg=e.message) + "```")
            log.exception(e)
            return
        except VkException as e:
            await ctx.send(
                _("An unexpected exception was raised when trying to retrieve user wall information. Try "
                  "again later."))
            log.exception(e)
            return
        except discord.errors.Forbidden as e:
            await ctx.send(
                _("I do not have access to this channel. Please give it to me and try again."))
            log.exception(e)
            return
        current_channels.append(channel_obj)
        await self.config.custom(WALLS_KEY, str(wall_id)).channels.set(current_channels)
        await self.config.custom(WALLS_KEY, str(wall_id)).last_date.set(post['date'])
        await ctx.send(_("Channel \"{channel}\" has successfully subscribed to updates on this wall!")
                       .format(channel=channel.mention))

    @vkhook.command(alias="unsub")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_webhooks=True)
    async def unsubscribe(self, ctx: commands.Context, channel: discord.TextChannel, wall_id: int = None):
        """
        Unsubscribes the channel from VK wall updates.
        If wall_id is not specified, will unsubscribe from all walls.

        Usage: [p]vkhook unsubscribe <channel> [wall_id]
        """
        if wall_id is not None:
            current_channels = await self.config.custom(WALLS_KEY, str(wall_id)).channels()
            to_del = [index for index, item in enumerate(current_channels)
                      if item['channel_id'] == channel.id and
                      item['guild_id'] == ctx.guild.id]
            if len(to_del) == 0:
                await ctx.send(_("Nothing to unsubscribe!"))
                return
            for d in to_del:
                del current_channels[d]
            if len(current_channels) > 0:
                await self.config.custom(WALLS_KEY, str(wall_id)).channels.set(current_channels)
            else:
                await self.config.custom(WALLS_KEY, str(wall_id)).clear()
            await ctx.send(_("Successfuly unsubscribed wall ``{wall}`` from channel {channel}")
                           .format(wall=wall_id, channel=channel.mention))
        else:
            walls = await self.config.custom(WALLS_KEY).all()
            walls_unsubscribed = []
            for wall_id, wall_data in walls.items():
                to_del = [index for index, item in enumerate(wall_data['channels'])
                          if item['channel_id'] == channel.id and
                          item['guild_id'] == ctx.guild.id]
                if len(to_del) == 0:
                    continue
                current_channels = wall_data['channels'].copy()
                for d in to_del:
                    del current_channels[d]
                if len(current_channels) > 0:
                    await self.config.custom(WALLS_KEY, str(wall_id)).channels.set(current_channels)
                else:
                    await self.config.custom(WALLS_KEY, str(wall_id)).clear()
                walls_unsubscribed.append(wall_id)
            if len(walls_unsubscribed) == 0:
                await ctx.send(_("Nothing to unsubscribe!"))
                return
            await ctx.send(_("Successfully unsubscribed wall(s) ``{walls}`` from channel {channel}")
                           .format(walls=", ".join(walls_unsubscribed), channel=channel.mention))

    @vkhook.command(alias=["reload"])
    @commands.is_owner()
    async def reload_walls(self, ctx: commands.Context):
        """
        Immediately checks all wall updates. Only for bot's owner!
        """

        await ctx.send(
            _("Walls in all guilds will be reloaded immediately.\nThe next update will take place in three minutes.")
        )

        self.update_walls_job.restart()

    async def get_account(self, wall_id: int, service_key: str) -> dict:
        session = vk.Session()
        session.access_token = service_key

        api = vk.API(session=session)

        if wall_id < 0:
            # Community wall
            return api.groups.getById(group_id=-wall_id, v=VK_VERSION)[0]

        else:
            # User wall
            return api.users.get(user_ids=wall_id, fields="photo_50", name_case="nom", v=VK_VERSION)[0]

    async def clear_wall(self, wall_id: int):
        await self.config.custom(WALLS_KEY, str(wall_id)).clear()

    async def clear_channel(self, channel_id: int, guild_id: int):
        walls = self.config.custom(WALLS_KEY).all()
        for wall_id, channels in walls.items():
            to_del = [index for index, item in enumerate(channels)
                      if item['channel_id'] == channel_id and
                      item['guild_id'] == guild_id]
            if len(to_del) == 0:
                continue
            current_channels = channels.copy()
            for d in to_del:
                del current_channels[d]
            if len(current_channels) > 0:
                await self.config.custom(WALLS_KEY, str(wall_id)).channels.set(current_channels)
            else:
                await self.config.custom(WALLS_KEY, str(wall_id)).clear()

    async def send_posts_from_wall(
            self,
            posts: list,
            account: dict,
            channel: discord.TextChannel,
            service_key: str,
            color: discord.Colour = None):
        session = vk.Session()
        session.access_token = service_key

        api = vk.API(session=session)

        if color is None:
            color = await self.bot.get_embed_color(channel)

        wall_id = posts[0]['from_id']

        for post in posts:
            embed = Embed(color=color)
            embed.title = account['name'] if wall_id < 0 else account['first_name'] + " " + account['last_name']
            embed.description = post['text']
            if 'copy_history' in post:
                embed.description += "\n\n"
                embed.description += post['copy_history'][0]['text']

            embed.url = get_post_url(wall_id, post['id'])
            embed.set_author(
                name=embed.title,
                url="https://vk.com/club" + str(-wall_id) if wall_id < 0 else ("https://vk.com/id" + str(wall_id)),
                icon_url=account['photo_50']
            )

            image_url = get_good_photo(post=post)
            if image_url is not None:
                embed.set_image(url=image_url)
            elif image_url is None and 'copy_history' in post:
                image_url = get_good_photo(post=post['copy_history'][0])
                if image_url is not None:
                    embed.set_image(url=image_url)

            embed.set_footer(text='\u200b')
            timestamp = post['date']
            date = datetime.datetime.fromtimestamp(timestamp)
            embed.timestamp = date

            await channel.send(embed=embed)

