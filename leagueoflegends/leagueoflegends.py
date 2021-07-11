import asyncio
import json

from discord import Message, Embed, Guild, TextChannel
import discord
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.chat_formatting import humanize_number
from redbot.core import commands, Config, bot as RedBot, errors, i18n
from redbot.core.commands import UserInputOptional
from redbot.core.i18n import Translator, cog_i18n
from json import JSONEncoder, JSONDecoder

from riotwatcher import LolWatcher, ApiError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.triggers.interval import IntervalTrigger

from random import Random

from .log import log

datadragon_version = "11.14.1"

tiers_order = {
    "IRON": 9,
    "BRONZE": 8,
    "SILVER": 7,
    "GOLD": 6,
    "PLATINUM": 5,
    "DIAMOND": 4,
    "MASTER": 3,
    "GRANDMASTER": 2,
    "CHALLENGER": 1,
}

ranks_order = {
    "I": 1,
    "II": 2,
    "III": 3,
    "IV": 4
}

_ = Translator("LeagueOfLegends", __file__)

@cog_i18n(_)
class LeagueOfLegends(commands.Cog):
    """LeagueOfLegends API related commands."""

    def __init__(self, bot: RedBot, *args, **kwargs):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=13371448228)
        default_guild = {
            "enable_leaderboard": False,
            "leaderboard_channel": -1,
            "current_messages": []
        }
        default_user = {
            "summoner_name": "",
            "region": "",
            "account_id": "",
            "puuid": "",
            "summoner_id": ""
        }
        self.config.register_guild(**default_guild)
        self.config.register_user(**default_user)
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.leaderboard_update_job, IntervalTrigger(hours=1))
        self.scheduler.start()

        super().__init__(*args, **kwargs)

    def cog_unload(self):
        self.scheduler.remove_all_jobs()
        self.scheduler.shutdown()
        self.session.detach()

    async def leaderboard_update_job(self):
        log.info("Started scheduled task")

        api_key = await self.get_api_key()

        lol = LolWatcher(api_key=api_key)

        ranked_infos = {}

        guilds = await self.config.all_guilds()

        summoners = await self.config.all_users()

        for user_id in summoners.keys():
            config = summoners[user_id]

            if config['summoner_name'] is None or config['summoner_name'] == "" or \
                config['region'] is None or config['region'] == "":
                continue # escape

            summoner_id = config['summoner_id']

            if summoner_id is None or summoner_id == "":
                # doesn't have summoner id - so get it from api
                while True:
                    try:
                        summoner = lol.summoner.by_name(config['region'], config['summoner_name'])
                        await self.config.user_from_id(user_id=user_id).account_id.set(summoner['accountId'])
                        await self.config.user_from_id(user_id=user_id).puuid.set(summoner['puuid'])
                        await self.config.user_from_id(user_id=user_id).summoner_id.set(summoner['id'])
                        break
                    except ApiError as err:
                        if err.response.status_code == 429:
                            await asyncio.sleep(int(err.header['Retry-After']))
                            continue
                        else:
                            # it's not quota exceed - skip
                            break
                    except Exception as err:
                        log.exception(f"can't get summoner_id by leaderboard for {config['summoner_name']}#{config['region']}", exc_info=Exception)
                        break

            if summoner_id is None or summoner_id == "":
                continue

            # after all we got a valid summoner_id
            # now we need to get ranked info
            ranked_info = []

            # {'id': 'v6InAqLEJyqAn1q5BDXhBcFa7vwMDtTcijHlADRJa0o1', 'accountId': 'Na5HRo2TcALrgLtWGlrJav9IeyfeAJuiGGGJPn2QUC9ht9o', 'puuid': 'AoQiI83Fptup1ZZxVTuLCt_4fGJAyD5v9-8niNHwRRlRhSEuV8CJIZtD5z1Wq5T6AkIMpe_m2nZPNQ', 'name': 'BMPX', 'profileIconId': 4987, 'revisionDate': 1625675786000, 'summonerLevel': 238}
            while True:
                try:
                    ranked_info = lol.league.by_summoner(config['region'], summoner_id)

                    for i, v in enumerate(ranked_info):
                        ranked_info[i]['tier_int'] = tiers_order[ranked_info[i]['tier']]
                        ranked_info[i]['rank_int'] = ranks_order[ranked_info[i]['rank']]

                    ranked_infos[user_id] = ranked_info
                    break
                except ApiError as err:
                        if err.response.status_code == 429:
                            await asyncio.sleep(int(err.header['Retry-After']))
                            continue
                        else:
                            # it's not quota exceed - skip
                            break
                except Exception as err:
                    log.exception(f"can't get summoner_id by leaderboard for {config['summoner_name']}#{config['region']}", exc_info=Exception)
                    break

        for guild_id in guilds.keys():
            guild = self.bot.get_guild(guild_id)

            current_messages = await self.config.guild(guild).current_messages()
            channel_id = await self.config.guild(guild).leaderboard_channel()

            if channel_id is not int and channel_id == -1:
                continue

            if (await self.config.guild(guild).enable_leaderboard()) is not True:
                continue

            guild_summoners = ranked_infos.copy()

            for user_id in ranked_infos.keys():
                if not guild.get_member(user_id):
                    del guild_summoners[user_id]

            channel = discord.utils.get(guild.text_channels, id=channel_id)
            embed_colour = await self.bot.get_embed_color(channel)
            for message_id in current_messages:
                try:
                    await channel.delete_messages([channel.get_partial_message(message_id=message_id)])
                except Exception:
                    log.exception("Can't delete message from text channel (maybe no permission?)", exc_info=Exception)

            if len(guild_summoners) == 0:
                continue

            # [{'leagueId': '6f6447e1-f58a-38be-a252-322a480e9867', 'queueType': 'RANKED_SOLO_5x5', 'tier': 'CHALLENGER',
            #   'rank': 'I', 'summonerId': 'v6InAqLEJyqAn1q5BDXhBcFa7vwMDtTcijHlADRJa0o1', 'summonerName': 'BMPX',
            #   'leaguePoints': 811, 'wins': 462, 'losses': 405, 'veteran': True, 'inactive': False, 'freshBlood': False,
            #   'hotStreak': False},
            #  {'leagueId': '374f3a69-5147-43e0-b193-219017cd737b', 'queueType': 'RANKED_FLEX_SR', 'tier': 'PLATINUM',
            #   'rank': 'I', 'summonerId': 'v6InAqLEJyqAn1q5BDXhBcFa7vwMDtTcijHlADRJa0o1', 'summonerName': 'BMPX',
            #   'leaguePoints': 58, 'wins': 81, 'losses': 51, 'veteran': False, 'inactive': False, 'freshBlood': False,
            #   'hotStreak': False}]

            queues = ['RANKED_SOLO_5x5', 'RANKED_FLEX_SR']
            current_messages = []

            for queue in queues:
                embed = Embed(title=f"Leaderboard for {queue} queue", colour=embed_colour)

                queue_summoners = []

                for guild_summoner in guild_summoners.keys():
                    for q in guild_summoners[guild_summoner]:
                        if q['queueType'] == queue:
                            qu = q.copy()
                            qu['discord_id'] = guild_summoner
                            queue_summoners.append(qu)

                queue_summoners = sorted(queue_summoners.copy(), key=lambda k: (k['tier_int'], k['rank_int']))

                for i in range(0, 9):
                    try:
                        summoner = queue_summoners[i]
                    except IndexError:
                        break
                    else:
                        user = discord.utils.get(self.bot.users, id=summoner['discord_id'])
                        embed.add_field(
                            name=f"#{i+1}",
                            value=f"{summoner['summonerName']} ({user.mention}) - {summoner['tier']} {summoner['rank']}",
                            inline=False
                        )

                current_messages.append((await channel.send(embed=embed)).id)

            await self.config.guild(guild).current_messages.set(current_messages)

    async def get_api_key(self, ctx: commands.Context = None):
        api_keys = await self.bot.get_shared_api_tokens("leagueoflegends")
        if api_keys is None and ctx is not None:
            await ctx.send("Error! League Of Legends ``api_key`` is not provided! Set it by ``[p]set api "
                           "leagueoflegends api_key,[YOUR API TOKEN]``.")
        return api_keys.get("api_key")

    @commands.group()
    async def lol(self, ctx: commands.Context):
        """League of Legends related commands"""

        pass

    @lol.command(alias=["set_name"])
    async def setname(self, ctx:commands.Context):
        """Sets the "Summoner name" for the user"""

        await ctx.send("Send a proper ``Summoner name``")

        try:
            msg = await self.bot.wait_for(
                "message",
                check=MessagePredicate.same_context(ctx),
                timeout=30
            )
        except asyncio.TimeoutError:
            await ctx.send("Time is out. Cancelled.")
        else:
            await self.config.user(ctx.author).summoner_name.set(msg.content)
            await self.config.user(ctx.author).account_id.set("")
            await self.config.user(ctx.author).puuid.set("")
            await self.config.user(ctx.author).summoner_id.set("")
            await ctx.send("Your name is set as \""+await self.config.user(ctx.author).summoner_name()+"\"")

    async def getLocale(self, ctx):
        return await i18n.get_locale_from_guild(self.bot, ctx.guild)

    @lol.command(alias=["set_region"])
    async def setregion(self, ctx: commands.Context):
        """Sets the region for the user"""

        valid_region_codes = {
            "EUW": "Europe West",
            "EUNE": "Europe Nordic & East",
            "NA": "North America",
            "BR": "Brazil",
            "RU": "Russia",
            "TR": "Turkey",
            "OC1": "Oceania",
            "LA1": "Latin America North",
            "LA2": "Latin America South",
            "JP": "Japan",
            "PH": "Philippine",
            "SG": "Singapore",
            "TH": "Thailand",
            "TW": "Taiwan",
            "VN": "Vietnam"
        }
        embed = Embed(
            description="Send a proper ``Region code`` e.g.:",
            colour=await ctx.embed_colour()
        )
        for code in valid_region_codes.keys():
            embed.add_field(
                name=code,
                value=valid_region_codes[code],
                inline=True
            )
        await ctx.send(embed=embed)

        try:
            msg = await self.bot.wait_for(
                "message",
                check=MessagePredicate.same_context(ctx),
                timeout=30
            )
        except asyncio.TimeoutError:
            await ctx.send("Time is out. Cancelled.")
        else:
            region = str.upper(msg.content)
            if region not in valid_region_codes:
                await ctx.send("This is not valid ``Region code``!")
                return
            await self.config.user(ctx.author).region.set(msg.content)
            await self.config.user(ctx.author).account_id.set("")
            await self.config.user(ctx.author).puuid.set("")
            await self.config.user(ctx.author).summoner_id.set("")
            await ctx.send("Your region is set as ``" + await self.config.user(ctx.author).region() + "`` ("+valid_region_codes[region]+")")

    @lol.command()
    async def userstats(self, ctx: commands.Context):
        """Returns stats of provided user"""

        # Check name
        summoner_name = await self.config.user(ctx.author).summoner_name()
        if summoner_name is None:
            await ctx.send("You did not set a ``Summoner name``! You can do this with this command: ``"+ctx.prefix+"lol setname``")
            return

        # Check region
        region = await self.config.user(ctx.author).region()
        if region is None:
            await ctx.send("You did not set a ``Region``! You can do this with this command: ``"+ctx.prefix+"lol setregion``")
            return

        region = str.lower(region)

        api_key = await self.get_api_key(ctx)
        if api_key is None:
            return

        lol = LolWatcher(api_key)

        try:
            summoner = lol.summoner.by_name(
                summoner_name=summoner_name,
                region=str.lower(region)
            )
            await self.config.user(ctx.author).puuid.set(summoner['puuid'])
            await self.config.user(ctx.author).account_id.set(summoner['accountId'])
            await self.config.user(ctx.author).summoner_id.set(summoner['id'])
        except ApiError as err:
            global embed
            if err.response.status_code == 404:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Summoner not found!",
                    color=0xff0000
                )

            elif err.response.status_code == 429:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Unfortunately, can't get your stats because the Riot API quota was fully used. "
                                "The quota will be restored in ``{} seconds``.".format(err.header["Retry-After"]),
                    color=0xff0000
                )
                await ctx.send(embed=embed)
            elif err.response.status_code == 403:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Couldn't get your stats because API key expired or cancelled.",
                    color=0xff0000
                )

            await ctx.send(embed=embed)
            return

        embed = Embed(title="Summoner statistics", colour=await ctx.embed_colour())

        embed.set_author(name=summoner["name"])

        embed.add_field(name="Level", value=str(summoner["summonerLevel"]), inline=True)

        embed.set_footer(text="League of Legends RED Cog developed by NukDokPlex using RiotWatcher wrapper")
        embed.set_thumbnail(
            url=f"http://ddragon.leagueoflegends.com/cdn/{datadragon_version}/img/profileicon/{str(summoner['profileIconId'])}.png"
        )

        await ctx.send(embed=embed)

        try:
            rankedInfo = lol.league.by_summoner(region=region, encrypted_summoner_id=summoner['id'])
        except ApiError as err:

            if err.response.status_code == 404:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Summoner not found!",
                    color=0xff0000
                )

            elif err.response.status_code == 429:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Unfortunately, can't get your stats because the Riot API quota was fully used. "
                                "The quota will be restored in ``{} seconds``.".format(err.header["Retry-After"]),
                    color=0xff0000
                )
                await ctx.send(embed=embed)
            elif err.response.status_code == 403:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Couldn't get your stats because API key expired or cancelled.",
                    color=0xff0000
                )

            await ctx.send(embed=embed)
            return

        # [{'leagueId': '6f6447e1-f58a-38be-a252-322a480e9867', 'queueType': 'RANKED_SOLO_5x5', 'tier': 'CHALLENGER',
        #   'rank': 'I', 'summonerId': 'v6InAqLEJyqAn1q5BDXhBcFa7vwMDtTcijHlADRJa0o1', 'summonerName': 'BMPX',
        #   'leaguePoints': 811, 'wins': 462, 'losses': 405, 'veteran': True, 'inactive': False, 'freshBlood': False,
        #   'hotStreak': False},
        #  {'leagueId': '374f3a69-5147-43e0-b193-219017cd737b', 'queueType': 'RANKED_FLEX_SR', 'tier': 'PLATINUM',
        #   'rank': 'I', 'summonerId': 'v6InAqLEJyqAn1q5BDXhBcFa7vwMDtTcijHlADRJa0o1', 'summonerName': 'BMPX',
        #   'leaguePoints': 58, 'wins': 81, 'losses': 51, 'veteran': False, 'inactive': False, 'freshBlood': False,
        #   'hotStreak': False}]

        for info in rankedInfo:
            embed = Embed(title="Statistics for "+info["queueType"], colour=await ctx.embed_colour())
            embed.set_author(name=summoner["name"])
            embed.set_thumbnail(
                url="https://nukdotcom.ru/wp-content/uploads/2021/07/" + info["tier"] + ".png"
            )
            embed.add_field(name="Tier", value=info["tier"], inline=True)
            embed.add_field(name="Rank", value=info["rank"], inline=True)
            embed.add_field(name="League points", value=str(info["leaguePoints"]), inline=True)
            embed.add_field(name="Wins", value=str(info["wins"]), inline=True)
            embed.add_field(name="Losses", value=str(info["losses"]), inline=True)
            winrate = float(info["wins"] / (info["wins"] + info["losses"])) * 100
            embed.add_field(name="Winrate", value=humanize_number(winrate, await self.getLocale(ctx))+"%")

            statuses = [
                {'name': "veteran", 'nice': "Veteran"},
                {'name': "inactive", 'nice': "Inactive"},
                {'name': "freshBlood", 'nice': "Fresh Blood"},
                {'name': "hotStreak", 'nice': "Hot Streak"}
            ]
            statusesToDisplay = []
            for status in statuses:
                if info[status['name']] is True:
                    statusesToDisplay.append(status['nice'])

            statuses_str = ""

            i = 0
            while i <= len(statusesToDisplay)-2:
                statuses_str += statusesToDisplay[i]
                statuses_str += ", "
                i += 1

            if len(statusesToDisplay) > 0:
                statuses_str += statusesToDisplay[len(statusesToDisplay)-1]
            else:
                statuses_str = "-"

            embed.add_field(name="Status", value=statuses_str, inline=True)

            await ctx.send(embed=embed)

    @lol.command()
    @commands.guild_only()
    @commands.guildowner()
    async def setup_leaderboard(self, ctx):
        """Setup League Of Legends"""
        await ctx.send("Send a proper text channel with ``#`` prefix.")
        pred = MessagePredicate.same_context(ctx).valid_text_channel(ctx)
        try:
            msg = await self.bot.wait_for(
                "message",
                check=pred,
                timeout=30
            )
        except asyncio.TimeoutError:
            await ctx.send("Time is out. Cancelled.")
            return
        else:
            channel = msg.channel_mentions[0].id

            await self.config.guild(ctx.guild).leaderboard_channel.set(channel)
            await self.config.guild(ctx.guild).enable_leaderboard.set(True)

            await ctx.send("You selected "+msg.content+" channel. This channel will now update the leaderboard every "
                                                       "hour with users who have already set their ``Summoner name`` "
                                                       "and ``Region``. To set it, use the commands ``[p]lol setname`` "
                                                       "and ``[p]lol setregion``. Only correct ones will be added to "
                                                       "the leaderboard!")

    @lol.command()
    @commands.guild_only()
    @commands.guildowner()
    async def enable_leaderboard(self, ctx):
        """Enables League Of Legends leaderboard for this guild"""

        await self.config.guild(ctx.guild).enable_leaderboard.set(True)

        await ctx.send("Leaderboard has been enabled for this guild!")

    @lol.command()
    @commands.guild_only()
    @commands.guildowner()
    async def disable_leaderboard(self, ctx):
        """Disables League Of Legends leaderboard for this guild"""

        await self.config.guild(ctx.guild).enable_leaderboard.set(False)

        await ctx.send("Leaderboard has been disabled for this guild!")

    @lol.command()
    @commands.is_owner()
    async def reload_leaderboards(self, ctx: commands.Context):
        """Reload all League of Legends leaderboards"""

        await ctx.send("Leaderboards in all guilds will be reloaded immediately.\nThe next update will take place in one hour.")
        self.scheduler.shutdown()
        await self.leaderboard_update_job()
        self.scheduler.start()

    @lol.command(name="lastmatch")
    async def _lol_lastmatch(self, ctx: commands.Context):
        """Returns summoner's last match info"""



        # Check name
        summoner_name = await self.config.user(ctx.author).summoner_name()
        if summoner_name is None:
            await ctx.send(
                "You did not set a ``Summoner name``! You can do this with this command: ``" + ctx.prefix + "lol setname``")
            return

        # Check region
        region = await self.config.user(ctx.author).region()
        if region is None:
            await ctx.send(
                "You did not set a ``Region``! You can do this with this command: ``" + ctx.prefix + "lol setregion``")
            return

        region = str.lower(region)

        api_key = await self.get_api_key(ctx)
        if api_key is None:
            return

        lol = LolWatcher(api_key)

        try:
            summoner = lol.summoner.by_name(
                summoner_name=summoner_name,
                region=str.lower(region)
            )
        except ApiError as err:
            if err.response.status_code == 404:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Summoner not found!",
                    color=0xff0000
                )

            elif err.response.status_code == 429:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Unfortunately, can't get your stats because the Riot API quota was fully used. "
                                "The quota will be restored in ``{} seconds``.".format(err.header["Retry-After"]),
                    color=0xff0000
                )
                await ctx.send(embed=embed)
            elif err.response.status_code == 403:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Couldn't get your stats because API key expired or cancelled.",
                    color=0xff0000
                )
            else:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Unexpected error, see logs for details.",
                    color=0xff0000
                )
                log.exception("Got error while getting summoner's last match!", exc_info=err)

            await ctx.send(embed=embed)
            return
        """
        {'id': 'v6InAqLEJyqAn1q5BDXhBcFa7vwMDtTcijHlADRJa0o1', 'accountId': 'Na5HRo2TcALrgLtWGlrJav9IeyfeAJuiGGGJPn2QUC9ht9o', 'puuid': 'AoQiI83Fptup1ZZxVTuLCt_4fGJAyD5v9-8niNHwRRlRhSEuV8CJIZtD5z1Wq5T6AkIMpe_m2nZPNQ', 'name': 'BMPX', 'profileIconId': 4987, 'revisionDate': 1625675786000, 'summonerLevel': 238}
        """

        regions_translations = {
            "na": "americas",
            "br": "americas",
            "lan": "americas",
            "las": "americas",
            "oce": "americas",
            "kr": "asia",
            "jp": "asia",
            "eune": "europe",
            "euw": "europe",
            "tr": "europe",
            "ru": "europe"

        }

        try:
            match_ids = lol.match_v5.matchlist_by_puuid(
                region=regions_translations[region],
                puuid=summoner["puuid"],
                start=0,
                count=1
            )
        except ApiError as err:

            if err.response.status_code == 404:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Summoner not found!",
                    color=0xff0000
                )

            elif err.response.status_code == 429:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Unfortunately, can't get your stats because the Riot API quota was fully used. "
                                "The quota will be restored in ``{} seconds``.".format(err.header["Retry-After"]),
                    color=0xff0000
                )
                await ctx.send(embed=embed)
            elif err.response.status_code == 403:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Couldn't get your stats because API key expired or cancelled.",
                    color=0xff0000
                )
            else:
                embed = Embed(
                    title="Got error while getting summoner's stats!",
                    description="Unexpected error, see logs for details.",
                    color=0xff0000
                )
                log.exception("Got error while getting summoner's last match!", exc_info=err)

            await ctx.send(embed=embed)
            return

        if len(match_ids) < 1:
            await ctx.send("Can't find any match for you... Maybe you didn't play any?")
            return

        match_id = match_ids[0]

        try:
            match = lol.match_v5.by_id(region=regions_translations[region], match_id=match_id)
        except ApiError as err:
            if err.response.status_code == 404:
                embed = Embed(
                    title="Got error while getting summoner's match info!",
                    description="Summoner not found!",
                    color=0xff0000
                )

            elif err.response.status_code == 429:
                embed = Embed(
                    title="Got error while getting summoner's match info!",
                    description="Unfortunately, can't get your stats because the Riot API quota was fully used. "
                                "The quota will be restored in ``{} seconds``.".format(err.header["Retry-After"]),
                    color=0xff0000
                )
                await ctx.send(embed=embed)
            elif err.response.status_code == 403:
                embed = Embed(
                    title="Got error while getting summoner's match info!",
                    description="Couldn't get your stats because API key expired or cancelled.",
                    color=0xff0000
                )
            else:
                embed = Embed(
                    title="Got error while getting summoner's match info!",
                    description="Unexpected error, see logs for details.",
                    color=0xff0000
                )
                log.exception("Got error while getting summoner's last match info!", exc_info=err)

            await ctx.send(embed=embed)
            return

        stats = {}

        for participant in match['info']['participants']:
            if participant['puuid'] == summoner['puuid']:
                stats = participant

        embed = Embed(title="Win!" if stats['win'] is True else "Defeat!", colour=await ctx.embed_colour())

        embed.set_author(name=stats['summonerName']+" as "+stats['championName'])

        embed.set_thumbnail(url=f"https://ddragon.leagueoflegends.com/cdn/{datadragon_version}/img/champion/{str(stats['championName']).replace(' ', '')}.png")
        embed.add_field(name="Kills", value=str(stats['kills']), inline=True)
        embed.add_field(name="Deaths", value=str(stats['deaths']), inline=True)
        embed.add_field(name="Assists", value=str(stats['assists']), inline=True)
        embed.add_field(name="Position", value=str(stats['lane']).lower().capitalize())
        embed.add_field(
            name="Gold spent",
            value=f"{str(stats['goldSpent'])}/{str(stats['goldEarned'])}",
            inline=True
        )
        embed.add_field(
            name="Champion level",
            value=str(stats['champLevel']),
            inline=True
        )

        if stats['firstBloodKill'] is True:
            embed.add_field(
                name="First blood",
                value="achieved!",
                inline=True
            )

        if stats['firstTowerKill'] is True:
            embed.add_field(
                name="First tower",
                value="achieved!",
                inline=True
            )

        if stats['pentaKills'] is not None and stats['pentaKills'] > 0:
            embed.add_field(
                name="Penta Kills!",
                value=str(stats['pentaKills']),
                inline=True
            )

        if stats['quadraKills'] is not None and stats['quadraKills'] > 0:
            embed.add_field(
                name="Quadra Kills!",
                value=str(stats['quadraKills']),
                inline=True
            )

        await ctx.send(embed=embed)





