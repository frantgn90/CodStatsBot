import time
import urllib

from src.data.cod import CodStats
from src.model.accounts import AccountRepository, Account
from src.telegram.TelegramBot import TelegramBot


class CodStatusBot(TelegramBot):
    """
    This class is devoted to manage the CodStatusBotAccounts. The manager will divert the proper input command to the
    proper CodStatusBotAccount instance. One instance per account.
    """
    _update_offset = 0

    def __init__(self, telegram_bot_token: str):
        """
        Initialize the bot manager

        :param telegram_bot_token: The bot token (The one that BotFather gives you)
        """
        super(CodStatusBot, self).__init__(telegram_bot_token)

        # Gets the list of accounts for the TelegramBot
        self.accounts = AccountRepository()

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
        :raise Exception: Whether there is a problem communicating with the Telegram API
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
                user_id = update["message"]["from"]["id"]
                account = (self.accounts.get_bot_account_from_chat_id(chat_id)
                           or self.accounts.get_bot_account_from_user_id(user_id)
                           or Account.fake_account(chat_id, user_id))
                bot = (CodStatusBotAccount(self.telegram_bot_token, account)
                       if not account.fake_account else CodStatusBotSignUp(self.telegram_bot_token))

                if account.account_id not in self.cod_status_bots:
                    self.cod_status_bots.update({account.account_id: bot})
                self.cod_status_bots[account.account_id].process_update(update)

                # This offset should be updated in order to not get the same updates again
                self._update_offset = max(self._update_offset, update["update_id"] + 1)

            # Sometimes we can free space, let's do it here. For example when a bot has been there for a long time
            # without activity of the a sing up process is done
            removable_account_ids = [account_id for account_id, bot in self.cod_status_bots.items() if bot.removable]
            for account_id in removable_account_ids:
                del self.cod_status_bots[account_id]
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
    removable = False

    def __init__(self, telegram_bot_token: str, account: Account):
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
        This bot command just shows up startup welcome and instructions in case it is needed

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
        Returns a message with the level information for a given player in a
        given platform.

        :param args: <player_name> <player_platform>
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

    def _cmd_add_friend(self, args: list, update: dict):
        """
        Adds a friend to the squad. Take into account only the friends in the squad are gonna be taken into account
        on the real-time feeds updates

        :param args: <player_name> <player_platform>
        :param update:
        """
        chat_id = update["message"]["chat"]["id"]
        if len(args) != 2:
            self._send_message(chat_id, "Usage: /add_friend <player_name> <player_platform>")
            return
        player_name = urllib.parse.quote(args[0])
        player_platform = args[1]
        self._send_message(chat_id, f"Adding {player_name} to the squad... "
                                    f"Take into account that this user must be added as friend on the COD platform")
        try:
            self.account.add_player_to_group(chat_id, player_name, player_platform)
            self._send_message(chat_id, f"{player_name} has been added successfully!")
        except Exception:
            self._send_message(
                chat_id, f"Error adding {player_name} to the squad... :("
            )

    def _cmd_show_squad(self, args: list, update:dict):
        """
        Show information about the squad components
        :param args: All arguments are gonna be ignored
        :param update: The update object
        """
        chat_id = update["message"]["chat"]["id"]
        message = ""
        for cod_friend in self.account.get_cod_friends(chat_id):
            try:
                player_info = self.cod_stats.get_player_info(cod_friend.cod_player_name, cod_friend.cod_player_platform)
                player_level = player_info["data"]["level"]
                br_wins = player_info["data"]["lifetime"]["mode"]["br"]["properties"]["wins"]
                message += f"[{cod_friend.cod_player_name.replace('%23', '#')}] has the level [{player_level}] and BR wins [{br_wins}]\n"
            except Exception:
                self._send_message(
                    chat_id, f"Error getting info from the player {cod_friend.cod_player_name}... :("
                )
        self._send_message(chat_id, message)

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
        for cod_friend in self.account.get_cod_friends(chat_id):
            feed_info = self.cod_stats.get_scores_feed(last_time, cod_friend.cod_player_name,
                                                       cod_friend.cod_player_platform)
            matches = feed_info["matches"]
            if matches is None:
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

    def _handle_added_to_chat(self, chat_id: str, update: dict):
        """
        When the bot is added to a chat by a telegram user that already have an account, this chat is added
        as a new group where to publish for this account
        """
        if update["message"]["chat"]["type"] == "group":
            owner_name = update["message"]["from"]["username"]
            self._send_message(chat_id, "Hi guys! I am the CodStatusBot. I am gonna be pushing updates about the squad")
            self._send_message(chat_id, f"Please thanks to @{owner_name} for create the account")
            self._send_message(chat_id, "We are gonna use his/her COD account for retrieving the data")
            try:
                self.account.create_telegram_group(chat_id)
            except Exception as e:
                print(f"Something went wrong creating a new group. {e}")


class CodStatusBotNewChat(TelegramBot):
    def __init__(self, telegram_bot_token: str, account: Account):
        """
        Initialize the account manager

        :param account: The bot account
        """
        super().__init__(telegram_bot_token)
        self.account = account

        # Sign in in the COD platform
        self.cod_user, self.cod_password = account.cod_user, account.cod_password
        self.cod_stats = CodStats(self.cod_user, self.cod_password)


class CodStatusBotSignUp(TelegramBot):
    """
    This class is devoted to manage the sign up process in an specific chat
    """

    removable = False
    _waiting_for_the_user_name = False
    _waiting_for_the_user_password = False

    def __init__(self, telegram_bot_token: str):
        """
        Initialize the account manager
        """
        self.account_repository = AccountRepository()
        super().__init__(telegram_bot_token)

    def _cmd_start(self, args: list, update: dict):
        """
        This bot command just shows up startup welcome and instructions in case it is needed

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
            "Follow the instructions below:\n"
            "  1. Start a private conversation (if this is not a group you are done)\n"
            "  2. Call the command /new_account\n"
        )

    def _cmd_new_account(self, args: list, update: dict):
        """
        This command is for creating a new account. It will guide for the sign up process

        :param args:
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
            "After that you are gonna you will be able to go to a group of friends and tell me to show the information"
            " there",
        )
        self._send_message(
            chat_id,
            "If you agree, please tell me your Call of Duty profile webpage user",
        )
        self._waiting_for_the_user_name = True

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
                telegram_user_id = update["message"]["from"]["id"]
                new_account = self.account_repository.create(
                    self._temporal_cod_user_name, temporal_cod_user_password, chat_id, telegram_user_id
                )
                self._send_message(
                    chat_id, "Your account has been successfully created!"
                )
                self._send_message(
                    chat_id, "Congrats! From now on, you can use all the features!"
                )
                self._send_message(
                    chat_id,
                    "Also you can chat with me here, so tell me :) What do you want? "
                    "Type /help for a list of commands",
                )
                self.removable = True
            except Exception as e:
                self._send_message(
                    chat_id,
                    "Oh no! There might be some error processing your request :_(",
                )
                print(e)
