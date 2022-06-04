# NukDokPlex's Cogs
A collection of cogs developed by NukDokPlex with various functions

# Installation
Here are the Red commands to add this repository (use your bot's prefix in place of ``[p]``):
```
[p]load downloader
[p]repo add nukdokplex-cogs https://github.com/nukdokplex/nukdokplex-cogs
```

You may be prompted to respond with "I agree" after that.

# Cogs

You can install individual cogs like this:
```
[p]cog install nukdokplex-cogs [cog]
```

Just replace `[cog]` with the name of the cog you want to install.

## leagueoflegends

League of Legends related commands to watch statistics, create leaderboards on servers and much more.

The key feature is Guild Leaderboards

### Commands

A prefix is required before each of the above commands: ``[p] lol``

| Command               | Description                                                    |
|-----------------------|----------------------------------------------------------------|
| `setname`             | Sets the "Summoner name" for the user                          |
| `setregion`           | Sets the region for the user                                   |
| `setup_leaderboard`   | Setup League Of Legends leaderboard in server                  |
| `reload_leaderboards` | Reload all League of Legends leaderboards. Only for bot owner! |
| `enable_leaderboard`  | Enables League Of Legends leaderboard for this guild           |
| `disable_leaderboard` | Disables League Of Legends leaderboard for this guild          |
| `lastmatch`           | Returns summoner's last match info                             |
| `userstats`           | Find field values across all users                             |

### Credits

The cog uses [RiotWatcher](https://github.com/pseudonym117/Riot-Watcher) by [pseudonym117](https://github.com/pseudonym117) - a thin wrapper on top of the [Riot Games API for League of Legends](https://developer.riotgames.com/).

## licenseinfo_remover

Very-very-VERY bad plugin. What it means is that it does a very bad and wrong thing: it removes Red's built-in ``licenseinfo`` command. You are very bad person if you use it. Don't use that!

### Commands

There's no commands for this cog. It starts working as it was loaded.

## nicknameforcer

Another bad cog that is not working quite right at the moment. It will be fixed in time. Simply forces nickname for user by command.

### Commands

All commands works only for server admins. Every command starts with ``[p]nickforce`` or ``[p]nf``

| Command             | Description                                   |
|---------------------|-----------------------------------------------|
| `set`               | Sets the user to Nickname Force               |
| `unset`             | Unsets the user from Nickname Force           |

## vk_hook

This Cog serves as a webhook for the walls of users and groups in Europe's largest social network, [VKonakte](https://vk.com/).

### Commands

All commands works only for user, who can manage webhooks. Every command starts with ``[p]vkhook`` or ``[p]vkh``

| Command        | Description                                                |
|----------------|------------------------------------------------------------|
| `subscribe`    | Subscribes the channel to VK wall updates                  |
| `unsubscribe`  | Unsubscribes the channel from VK wall updates.             |
| `reload_walls` | Immediately checks all wall updates. Only for bot's owner! |

### Credits

This Cog using a tiny VKontakte API wrapper by [voronind](https://github.com/voronind) - [vk](https://github.com/voronind/vk).

# Contact
Use issues or see credits.

# Credits
NukDokPlex - [Website](https://nukdotcom.ru), [Blog](https://blog.nukdotcom.ru), Discord - NukDokPlex#6120