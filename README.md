# Call of Duty Stats bot for Telegram

This bot is devoted to provide Call of Duty videogame stats. For that end it provides a set of commands that are defined bellow. There are two points worth to mention:
- The mechanism for get the updates from the Telegram servers is through the `getUpdates` long latency call instead of webhooks. The reason is that for the moment I do not have a domain where to go.
- The call of duty stats API requires the login, so you must own a user in the platform. Furthermore the user stats that the bot can provide are only those users that have a friend relationship with the login account.

The *vision* of this project is to provide statistics, agregations, plots, live information, whatever to those groups of friends that shares a Telegram group. To have so, a given person on this group would need to speak first with the bot and take a token (paying a certain ammount of euros? and) providing the COD stats webpage credentials. Then after that it will add the bot to the group and provide its private token.

## Run the Telegram Bot

For running the bot you just need a machine with internet access and a Call of Duty platform (https://profile.callofduty.com/cod/login) account. The command you should run is
```
python main.py --cod_user <user> --cod_pass <password>
```
Following there is the usage of the bot
```
usage: main.py [-h] --cod_user COD_USER --cod_pass COD_PASS [--updates_timeout_s UPDATES_TIMEOUT_S]

Call of Duty stats Telegram bot

optional arguments:
  -h, --help            show this help message and exit
  --cod_user COD_USER   The COD platform user
  --cod_pass COD_PASS   The COD platform user
  --updates_timeout_s UPDATES_TIMEOUT_S
                        Timeout for taking updates from telegram
```

## Bot commands

Ammong all the update entities the Telegram API provides, for the moment this is only supporting `bot_commands`, i.e. 
those message with the form `/cmd param1 [param2 .. param_n]`.

Following there is a table with the currently supported commands.

| Command           | Params       | Description  |
|-------------------|--------------|--------------|
|`/start` | | Just answers with a funny start message |
|`/cod_level` | user platform | Answers with the level of the `user` in a given `platform`. There are several platforms out there. The most common used are `psn` for PlayStation and `uno` (unkown?) por PC |

Additionally if you type a command that the bot does not understand, you are gonna be responded with a reproach

### Adding bot commands

All the commands are handled by the main `CodStatsBot` class. There is straighforward to add new handlers,
 just add a new function into the class following the form below:
```
def __cmd_<cmd>(self, args: list, update: dict) -> None:
	pass
```

`<cmd>` is the command you want to handle, e.g. `__cmd_kissme` is gonna handle the command `/kissme`. The two parameters that must accept are:
- args: This is a list with the arguments values, e.g. for the command `/kissme in face` args will take the value `['in', 'face']`
- update: This is a dictionary with all the information about the update the Telegram API provides. For a complete description of this dictionary, please go to https://core.telegram.org/bots/api#update

## Repository structure

- `main.py` The entrypoint
- `src/`
- `src/cod_status_bot.py` The actual implementation of the bot
- `src/data` The data layer
- `src/data/cod.py` The actual interface with the call of duty stats API

