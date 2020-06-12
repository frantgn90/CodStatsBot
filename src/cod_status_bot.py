import time
import urllib

from src.data.cod import CodStats
from src.model.accounts import Accounts
from src.model.accounts import Account
from src.telegram.TelegramBot import TelegramBot


class CodStatusBot(TelegramBot):
    """
    This class is devoted to manage the CodStatusBot. The manager will divert the proper input command to the
    proper CodStatusBot instance. One instance per account
    """

    _update_offset = 0

    def __init__(self, telegram_bot_token: str):
        """
        Initialize the bot manager

        :param telegram_bot_token: The bot token (The one that BotFather gives you)
        """
        super(CodStatusBot, self).__init__(telegram_bot_token)

        # Gets the list of accounts for the TelegramBot
        self.accounts = Accounts()

        # Since it eagerly is loading the bots instances, depending on the updates, in order to be serving the
        #  real time feeds, this should be filled up with those accounts that have real-time feeds activated
        # If no activity after a certain time and it must not report anything, the bot account instance could be
        #  shut down
        self.cod_status_bots = {
            account.account_id: CodStatusBotAccount(self.telegram_bot_token, account)
            for account in self.accounts.get_feeds_activated_accounts()
        }

    def updates_polling(self, timeout_s: int = 1):
        """
        Checks for updates every certain time set by `period_ms`.

        :param timeout_s: Seconds before the long polling timeout
        :raise Exception: Whether there is a problem communicating with the
         Telegram API
        """
        while True:
            response = self._call_endpoint(
                "getUpdates",
                "POST",
                {"content-type": "application/json"},
                {"timeout": timeout_s, "offset": self._update_offset},
            )
            for update in response["result"]:
                chat_id = update["message"]["chat"]["id"]
                account = self.accounts.get_bot_account_from_chat_id(chat_id)
                if account.account_id not in self.cod_status_bots:
                    self.cod_status_bots.update(
                        {
                            account.account_id: CodStatusBotAccount(
                                self.telegram_bot_token, account
                            )
                            if account.account_id is not None
                            else CodStatusBotSignUp(self.telegram_bot_token)
                        }
                    )
                cod_status_bot = self.cod_status_bots[account.account_id]
                # When the process of signing up has been successful, the interaction is with an already logged in bot
                if (
                    isinstance(cod_status_bot, CodStatusBotSignUp)
                    and cod_status_bot.new_account_created
                ):
                    # TODO if we are joining a new group to an account we might end up with two different instances
                    #  of cod_status_bot for the same account!!!
                    cod_status_bot = CodStatusBotAccount(
                        self.telegram_bot_token, cod_status_bot.new_account
                    )
                    self.cod_status_bots[account.account_id] = cod_status_bot
                cod_status_bot.process_update(update)
                if update["update_id"] + 1 > self._update_offset:
                    self._update_offset = update["update_id"] + 1
            self._process_feeds()
            time.sleep(timeout_s)

    def _process_feeds(self):
        for _, cod_status_bot in self.cod_status_bots.items():
            cod_status_bot.process_loop()


class CodStatusBotAccount(TelegramBot):
    """
    This class is devoted to manage all te interactions with an specific chat
    TODO Some operations must be done at chat level, e.g. get the teammates level
    """

    def __init__(self, telegram_bot_token: str, account: object):
        """
        Initialize the account manager

        :param account: The bot account
        """
        super().__init__(telegram_bot_token)
        self.account = account

        # Sign in in the COD platform
        self.cod_user, self.cod_password = account.cod_user, account.cod_password
        self.cod_stats = CodStats(self.cod_user, self.cod_password)

    def _cmd_start(self, args: list, update: dict):
        """
        Telegram is used to send `/start` whenever a bot is added into a group.
        This bot command just shows up a funny welcome message.

        :param args: The args are gonna be ignored.
        :param update: The update information
        """
        chat_id = update["message"]["chat"]["id"]
        commands = "\n".join(
            [f"- /{fn_name}" for fn_name in self.bot_command_fn]
        ) + "\n".join([f"- /activate_{fn_name}" for fn_name in self.bot_loop_fn])
        self._send_message(
            chat_id,
            f"Hey there! I am the CodStatusBot, I am happy to be here with you guys. I will try to improve your COD "
            f"experience by sharing with you all your stats with nice aggregation and plots so that you can compare "
            f"them with your teammates and check out your evolution. Just to start, here there is a list of the"
            f"available operations: {commands}",
        )

    def _cmd_cod_level(self, args: list, update: dict):
        """
        This bot command returns a message with the level information for a given player in a
        given platform.

        :param args: It must be a two value list
            - player: Is the player name
            - platform: Is the platform from where we want to take the information
        """

        chat_id = update["message"]["chat"]["id"]
        if len(args) != 2:
            self._send_message(chat_id, "Usage: /cod_level <player> <platform>")
            return
        player_name = urllib.parse.quote(args[0])
        player_platform = args[1]
        self._send_message(chat_id, f"Getting information from player {player_name}...")
        try:
            player_info = self.cod_stats.get_player_info(player_name, player_platform)
            player_level = player_info["data"]["level"]
            self._send_message(chat_id, f"{player_name} has the level {player_level}!")
        except Exception:
            self._send_message(
                chat_id, f"Error getting info from the player {player_name}... :("
            )

    def _cmd_help(self, args: list, update: dict):
        feeds_cmds = "\n".join(
            [f"- /activate_{fn_name} <yes|no>" for fn_name in self.bot_loop_fn]
        )
        chat_id = update["message"]["chat"]["id"]
        self._send_message(
            chat_id,
            f"List of commands for this noice bot\n"
            f"- /start\n"
            f"- /cod_level <user> <platform>\n"
            f"{feeds_cmds}",
        )

    def _loop_activity_feeds(self, last_time: int, chat_id: str) -> bool:
        """
        Checks whether there is a new message in the update activity feed. If yes,
        it sends a new message to the chat with chat_id id

        :param last_time: This is the last time the function was executed
        :param chat_id: Is the chat_id of the chat where to send the messages

        :return: False whether the execution was skiped, True otherwise
        """
        if time.time() - last_time < 180:  # 3 minutes
            return False
        for feed in self.cod_stats.get_activity_feed(last_time):
            self._send_message(
                chat_id, f"New activity: {feed['username']} -> {feed['category']}"
            )
        return True

    def _loop_scores_feeds(self, last_time: int, chat_id: str) -> bool:
        """
        Checks whether there is a new message in the scores activity feed. If yes,
        it sends a new message to the chat with chat_id id

        :param last_time: This is the last time the function was executed
        :param chat_id: Is the chat_id of the chat where to send the messages

        :return: False whether the execution was skiped, True otherwise
        """
        if int(time.time() * 1000) - last_time < 60000:  # 1 minutes
            return False
        matches = self.cod_stats.get_scores_feed(
            last_time, self.account.cod_user, self.account.cod_platform
        )["matches"]
        if matches is None:  # It does mean there are no matches
            return False
        for match in matches:
            player_name = match["player"]["username"]
            player_xp = match["playerStats"]["totalXp"]
            player_kills = match["playerStats"]["kills"]
            player_deaths = match["playerStats"]["deaths"]
            self._send_message(
                chat_id,
                f"Match has finnished\n"
                f"[{player_name}]\n - XP:{player_xp}\n - Kills: {player_kills}\n - Deaths: {player_deaths}",
            )
        return True


class CodStatusBotSignUp(TelegramBot):
    """
    This class is devoted to manage the sign up process in an specific chat
    """

    _waiting_for_the_user_name = False
    _waiting_for_the_user_password = False
    new_account_created = False

    def __init__(self, telegram_bot_token: str):
        """
        Initialize the account manager
        """
        super().__init__(telegram_bot_token)

    def _cmd_start(self, args: list, update: dict):
        """
        Telegram is used to send `/start` whenever a bot is added into a group.
        This bot command just shows up a funny welcome message.

        :param args: The args are gonna be ignored.
        """
        chat_id = update["message"]["chat"]["id"]
        if len(args) > 0:
            self._send_message(
                chat_id, "Hey dude! This command does not expect parameters"
            )
        self._send_message(
            chat_id,
            "Hey there! It seems you do not have an account.\n"
            "Please provide your token using /cod_token <private-token>"
            "If you do not have a token yet, follow the instructions below:\n"
            "  1. Start a private conversation (if this is not a group you are done)\n"
            "  2. Call the command /new_account\n"
            "  3. Follow the steps to get your access token",
        )

    def _cmd_new_account(self, args: list, update: dict):
        """
        The new account command. This is the very entry point for the bot. This is gonna guide the user in order to
        obtain its private token

        :param args: The arguments for this command
        :param update: The whole update object
        """
        chat_id = update["message"]["chat"]["id"]
        self._send_message(
            chat_id,
            "First of all I want to welcome you. With this bot you are gonna be able to "
            "check out all your Call of Duty statistics and furthermore, compare them with you "
            "colleagues. Also you are gonna be able to receive live updates on you and colleagues "
            "activity",
        )
        self._send_message(
            chat_id,
            "To be able to access your data (and your friends), I need your permission. If I have so, then I would"
            " need your credentials for the https://profile.callofduty.com/cod/login webpage since"
            " this is the source of the data. I get it and beautify :) Do not worry, your credentials"
            " are gonna be saved in a way nobody else will never have access!",
        )
        self._send_message(
            chat_id,
            "After that you are gonna receive a secret access token. With this access token"
            " you will be able to go to a group of friends and tell me to show the information there",
        )
        self._send_message(
            chat_id,
            "If you agree, please tell me your Call of Duty profile webpage user",
        )
        self._waiting_for_the_user_name = True

    def _cmd_cod_token(self, args: list, update: dict):
        self.new_account = Account.get_account_by_token(args[0])
        chat_id = update["message"]["chat"]["id"]

        if self.new_account is not None:
            # TODO Add new group to the account
            # TODO Generate new private token and sent it to the user private chat
            self._send_message(chat_id, "You logged in successfully")
        else:
            self._send_message(chat_id, "There might be a problem with your token. Check you it is correct")

    def _handle_text_message(self, message: str, update: dict):
        """
        It handles only the text messages

        :param message: The text message
        """
        chat_id = update["message"]["chat"]["id"]
        if self._waiting_for_the_user_name:
            self._temporal_cod_user_name = message
            self._send_message(chat_id, "Nice! We received your username")
            self._send_message(chat_id, "Now, we need your password")
            self._waiting_for_the_user_name = False
            self._waiting_for_the_user_password = True
        elif self._waiting_for_the_user_password:
            temporal_cod_user_password = message
            self._waiting_for_the_user_password = False
            try:
                self.new_account = Account.new_account(
                    self._temporal_cod_user_name, temporal_cod_user_password, chat_id
                )
            except Exception as e:
                self._send_message(
                    chat_id,
                    "Oh no! There might be some error processing your request :_(",
                )
            else:
                self._send_message(
                    chat_id, "Your account has been successfully created!"
                )
                self._send_message(
                    chat_id, f"Your secret token is: {self.new_account.secret_token}"
                )
                self._send_message(
                    chat_id, "Congrats! From now on, you can use all the features!"
                )
                self._send_message(
                    chat_id,
                    "The token we provided should be used to invite me to your group of"
                    " teammates. Once you add me to the group, use the command /cod_token <token>",
                )
                self._send_message(
                    chat_id,
                    "Every time you use the token, a new one is gonna be generated for"
                    " security purposes and sent to you in this chat.",
                )
                self._send_message(
                    chat_id,
                    "Also you can chat with me here, so tell me :) What do you want? "
                    "Type /help for a list of commands",
                )
                self.new_account_created = True
