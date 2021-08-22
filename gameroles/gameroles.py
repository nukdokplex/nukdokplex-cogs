import discord
from redbot.core import commands
from redbot.core import Config
from redbot.core import checks
from redbot.core.utils.chat_formatting import humanize_list
from redbot.core.i18n import Translator, cog_i18n
from typing import Union
from .log import log

_ = Translator("GameRoles", __file__)


def get_game_playing(activities):
	"""Get a user now playing game (activity)."""
	if len(activities) == 0:
		return None
	for activity in activities:
		if activity.type == discord.ActivityType.playing:
			return activity
	return None


class GameRoles(commands.Cog):
	"""Grant roles when a user is playing a specific game."""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot = bot
		self.cache = {}
		self.config = Config.get_conf(self, identifier=13371448228)
		self.config.register_guild(
			roleActivities={},
			doAdd=True,
			doRemove=False
		)

	@commands.guild_only()
	@commands.group(aliases=['gr'])
	async def gameroles(self, ctx):
		"""Group command for game roles."""
		pass

	@checks.guildowner()
	@gameroles.command()
	async def addrole(self, ctx, role: discord.Role):
		"""
		Sets a role to be managed by gameroles.

		Roles with multiple words need to be surrounded in quotes.
		The bot's highest role needs to be above the role that you are adding and the bot needs permission to manage roles.
		"""
		roleActivities = await self.config.guild(ctx.guild).roleActivities()

		if role.id in roleActivities:
			return await ctx.send(_(
				'``{role_name}`` is already managed by gameroles. '
				'Use ``{prefix}gameroles addactivity`` to add activities.'
				).format(role_name=role.name, prefix=ctx.prefix)
			)
		roleActivities[role.id] = []
		await self.config.guild(ctx.guild).roleActivities.set(roleActivities)
		await ctx.send(
			_(
				'`{role_name}` is now managed by gameroles! '
				'Use `{prefix}gameroles addactivity` to add activities.'
			).format(role_name=role.name, prefix=ctx.prefix)
		)
		if ctx.guild.id in self.cache:
			del self.cache[ctx.guild.id]

	@checks.guildowner()
	@gameroles.command()
	async def delrole(self, ctx, role: Union[discord.Role, int]):
		"""
		Stop a role from being managed by gameroles.

		Roles with multiple words need to be surrounded in quotes.
		Accepts the ID of the role in case it was deleted.
		"""
		roleActivities = await self.config.guild(ctx.guild).roleActivities()
		if isinstance(role, discord.Role):
			rid = role.id
			name = role.name
		else:
			rid = role
			name = str(rid)
		if rid not in roleActivities:
			return await ctx.send(_('`{name}` is not managed by gameroles.').format(name=name))
		del roleActivities[rid]
		await self.config.guild(ctx.guild).roleActivities.set(roleActivities)
		await ctx.send(_('`{name}` is no longer managed by gameroles!').format(name=name))
		if ctx.guild.id in self.cache:
			del self.cache[ctx.guild.id]

	@checks.guildowner()
	@gameroles.command()
	async def addactivity(self, ctx, role: discord.Role, activity: Union[int, str]):
		"""
		Add an activity to trigger a role.

		Roles and activities with multiple words need to be surrounded in quotes.
		You can get the name of your current activity with [p]gameroles currentactivity.
		"""

		roleActivities = await self.config.guild(ctx.guild).roleActivities()

		if role.id not in roleActivities:
			return await ctx.send(_(
				'`{role_name}` is not managed by gameroles.'
			).format(role_name=role.name))
		if activity in roleActivities[role.id]:
			return await ctx.send(_(
				'`{activity}` already triggers `{role_name}`.'
			).format(activity=str(activity)), role_name=role.name)
		roleActivities[role.id].append(activity)
		await self.config.guild(ctx.guild).roleActivities.set(roleActivities)
		await ctx.send(_(
			'`{role_name}` is now triggered by `{activity}`!'
		).format(role_name=role.name, activity=str(activity)))
		if ctx.guild.id in self.cache:
			del self.cache[ctx.guild.id]

	@checks.guildowner()
	@gameroles.command()
	async def delactivity(self, ctx, role: discord.Role, activity: str):
		"""
		Remove an activity from triggering a role.

		Roles and activities with multiple words need to be surrounded in quotes.
		You can get the name of your current activity with [p]gameroles currentactivity.
		"""
		roleActivities = await self.config.guild(ctx.guild).roleActivities()
		rid = role.id
		if rid not in roleActivities:
			return await ctx.send(f'`{role.name}` is not managed by gameroles.')
		if activity not in roleActivities[rid]:
			return await ctx.send(f'`{activity}` does not trigger `{role.name}`.')
		roleActivities[rid].remove(activity)
		await self.config.guild(ctx.guild).roleActivities.set(roleActivities)
		await ctx.send(_(
			'`{role_name}` is no longer triggered by `{activity}`!'
		).format(role_name=role.name, activity=str(activity))
					   )
		if ctx.guild.id in self.cache:
			del self.cache[ctx.guild.id]

	@checks.guildowner()
	@gameroles.command()
	async def listroles(self, ctx):
		"""List the roles currently managed by gameroles."""

		roleActivities = await self.config.guild(ctx.guild).roleActivities()
		rolelist = []
		for role_id in roleActivities:
			role = ctx.guild.get_role(int(role_id))
			if role:
				rolelist.append(role.name)
		if not rolelist:
			return await ctx.send(_('Gameroles is currently not managing any roles.'))
		roles = '\n'.join(rolelist)
		await ctx.send(_(
			'Roles currently managed by gameroles:\n```\n{roles}```'
			).format(roles=roles)
		)

	@checks.guildowner()
	@gameroles.command()
	async def listactivities(self, ctx, role: discord.Role):
		"""
		List the activities that trigger a role.

		Roles with multiple words need to be surrounded in quotes.
		"""
		roleActivities = await self.config.guild(ctx.guild).roleActivities()

		if str(role.id) not in roleActivities:
			return await ctx.send(_('`{role_name}` is not managed by gameroles.').format(role_name=role.name))
		if not roleActivities[str(role.id)]:
			return await ctx.send(_(
				'`{role_name}` currently has no activities that trigger it.'
				).format(role_name=role.name)
			)
		activities = '\n'.join(roleActivities[str(role.id)])
		await ctx.send(
			_('Activities that currently trigger `{role_name}`:\n```\n{activities}```')
			.format(role_name=role.name, activities=activities)
		)

	@checks.guildowner()
	@gameroles.command()
	async def currentactivity(self, ctx):
		"""Get your current game playing."""
		game = get_game_playing(ctx.author.activities)

		if game is None:
			return await ctx.send(_("You're not playing anything right now."))
		else:
			await ctx.send(_("Your current game now is: ``{game}``").format(game=game.name))

	@gameroles.command()
	async def recheck(self, ctx):
		"""Force a recheck of your current activities."""
		if not ctx.guild.me.guild_permissions.manage_roles:
			return await ctx.send(_('I do not have permission to manage roles in this server.'))
		cfg = await self.config.guild(ctx.guild).all()

		current_managed_roles = set()
		to_add = set()
		failed = set()
		for role in ctx.author.roles:
			if str(role.id) in cfg['roleActivities']:
				if ctx.guild.me.top_role > role:
					current_managed_roles.add(role)
				else:
					failed.add(role)
		game = get_game_playing(ctx.author.activities)
		for role_id in [role_id for role_id in cfg['roleActivities'] if game.name in cfg['roleActivities'][role_id]]:
			role = ctx.guild.get_role(int(role_id))
			if role is not None and ctx.guild.me.top_role > role:
				to_add.add(role)
			elif role:
				failed.add(role)
		future_user_roles = current_managed_roles & to_add
		to_remove = current_managed_roles - future_user_roles
		to_add -= future_user_roles
		# Filter out managed roles like Nitro Booster
		to_remove = [role for role in to_remove if not role.managed]
		to_add = [role for role in to_add if not role.managed]
		if to_add and cfg['doAdd']:
			try:
				await ctx.author.remove_roles(*to_remove, reason=f'GameRoles managed by {ctx.guild.me.display_name}')
			except discord.errors.Forbidden:
				return await ctx.send(
					_('Encountered an unexpected discord.errors.Forbidden adding roles, canceling')
				)
		if to_remove and cfg['doRemove']:
			try:
				await ctx.author.remove_roles(*to_remove, reason=f'GameRoles managed by {ctx.guild.me.display_name}')
			except discord.errors.Forbidden:
				return await ctx.send(
					_('Encountered an unexpected discord.errors.Forbidden removing roles, canceling')
				)
		if failed:
			await ctx.send(
				_('The following roles could not be managed because they are higher than my highest role:\n`{list}`')
				.format(list=humanize_list(list(failed)))
			)
		await ctx.tick()

	@commands.guild_only()
	@checks.guildowner()
	@commands.group(aliases=['grset'], invoke_without_command=True)
	async def gameroleset(self, ctx):
		"""Config options for gameroles."""
		await ctx.send_help()
		data = await self.config.guild(ctx.guild).all()
		msg = _(
			'Add roles: {doAdd}\n'
			'Remove roles: {doRemove}\n'
		).format_map(data)
		await ctx.send(f'```py\n{msg}```')

	@gameroleset.command()
	async def add(self, ctx, value: bool = None):
		"""
		Set if roles should be added when someone starts playing a game.

		Defaults to True.
		This value is server specific.
		"""
		if value is None:
			v = await self.config.guild(ctx.guild).doAdd()
			if v:
				await ctx.send(_('Roles are added when someone starts playing.'))
			else:
				await ctx.send(_('Roles are not added when someone starts playing.'))
		else:
			await self.config.guild(ctx.guild).doAdd.set(value)
			if value:
				await ctx.send(_('Roles will now be added when someone starts playing.'))
			else:
				await ctx.send(_('Roles will no longer be added when someone starts playing.'))
			if ctx.guild.id in self.cache:
				del self.cache[ctx.guild.id]

	@gameroleset.command()
	async def remove(self, ctx, value: bool = None):
		"""
		Set if roles should be removed when someone stops playing a game.

		Defaults to True.
		This value is server specific.
		"""
		if value is None:
			v = await self.config.guild(ctx.guild).doRemove()
			if v:
				await ctx.send('Roles are removed when someone stops playing.')
			else:
				await ctx.send('Roles are not removed when someone stops playing.')
		else:
			await self.config.guild(ctx.guild).doRemove.set(value)
			if value:
				await ctx.send('Roles will now be removed when someone stops playing.')
			else:
				await ctx.send('Roles will no longer be removed when someone stops playing.')
			if ctx.guild.id in self.cache:
				del self.cache[ctx.guild.id]

	async def red_delete_data_for_user(self, **kwargs):
		"""Nothing to delete."""
		return

	@commands.Cog.listener(name="on_member_update")
	async def member_updated(self, before, after):
		"""Updates a member's roles."""

		if before.activities == after.activities:
			return  # User's activities not changed

		if await self.bot.cog_disabled_in_guild(self, after.guild):
			return  # Cog disabled in guild

		if not after.guild.me.guild_permissions.manage_roles:
			log.debug(
				f'I do not have manage_roles permission in {after.guild} (id: {after.guild.id}).'
			)
			return

		if after.guild.id not in self.cache:
			data = await self.config.guild(after.guild).all()
			self.cache[after.guild.id] = data
		# Guild doesn't existing in cache - adding it

		cache = self.cache[after.guild.id]

		if not cache['roleActivities']:
			return  # This guild has no set roles to manage

		if not (cache['doAdd'] or self.cache[after.guild.id]['doRemove']):
			return  # Nothing to do 'cause add and remove GameRoles options set off

		to_add, current_managing_roles = set(), set()
		# this sets will be used to store what roles will be added or deleted from user

		# Fill up to current managing roles
		# Going into detail, we are simply looking for intersections between
		# the list of roles we manage and the current roles of the user.
		# It will be known later why we do this.
		for role in after.roles:
			if str(role.id) in cache['roleActivities']:
				if after.guild.me.top_role > role:
					current_managing_roles.add(role)
				else:
					log.warning(
						f'Role {role} (id: role.id) from guild {after.guild} '
						f'(id: {after.guild.id}) is higher than my highest role.'
					)

		# Fill up to add list (more complicated intersections)

		# Getting a name of now playing game
		game = get_game_playing(after.activities)

		# Iterating each role id in role ids which exists in managing roles which linked to game
		if game:
			for role_id in [
				role_id
				for role_id in cache['roleActivities']
				if game.name in cache['roleActivities'][role_id]
			]:
				role = after.guild.get_role(role_id)
				if role is not None and after.guild.me.top_role > role:
					to_add.add(role)
				elif role:
					log.warning(
						f'Role {role} (id: {role.id}) from guild '
						f'{after.guild} (id: {after.guild.id}) is higher than my highest role.'
					)
				else:
					log.warning(
						f'Role {role_id} from guild {after.guild} (id: {after.guild.id}) '
						'may no longer exist.'
					)

		# This is tricky set which contains roles which will be added or not removed
		future_user_roles = current_managing_roles & to_add

		# We will delete roles which we managing except roles which will be added or not removed
		to_remove = current_managing_roles - future_user_roles

		# We will add roles which linked with now playing game except roles which already assigned to user
		to_add -= future_user_roles

		if not (to_remove or to_add):
			return  # Nothing to add or remove

		# Filter out managed roles like Nitro Booster
		to_remove = [role for role in to_remove if not role.managed]
		to_add = [role for role in to_add if not role.managed]

		# Removing roles
		if to_remove and cache['doRemove']:
			try:
				await after.remove_roles(*to_remove, reason=f'GameRoles managed by {after.guild.me.display_name}')
			except discord.errors.Forbidden:
				log.exception(
					'Encountered an unexpected discord.errors.Forbidden removing roles '
					f'from {after} in {after.guild} (id: {after.guild.id}).'
				)

		# And finally adding roles
		if to_add and cache['doAdd']:
			try:
				await after.add_roles(*to_add, reason=f'GameRoles managed by {after.guild.me.display_name}')
			except discord.errors.Forbidden:
				log.exception(
					'Encountered an unexpected discord.errors.Forbidden adding roles '
					f'from {after} in {after.guild} (id: {after.guild.id}).'
				)
