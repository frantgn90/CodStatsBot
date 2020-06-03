import requests
import time
import json
import os

from src.data.cod import CodStats

class CodStatusBot(object):
    _update_offset = 0

    def __init__(self, token: str, cod_user: str, cod_pwd: str, updates_webhook: str = None):
        """
        Initialize the communications with the Telegram Bot API 
        (https://core.telegram.org/bots/api).
        If the bot webhook has not been registrated it registrate it.

        :param token: The bot token (The one that BotFather gives you)
        :param cod_user: The user that is gonna be used for the login in the COD platform
        :param cod_pwd: The password that is gonna be used for the login in the COD platform
        """
        self.session = requests.Session() # This is not strictly necessary
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.me = self._get_me()

        # All methods that handles the bot_commands. These methods are gonna be called
        # Automatically, you just need to name it in the next manner:
        #   __cmd_<command_text>
        self.bot_command_fn = {
                fn_name.replace("_CodStatusBot__cmd_", ""): getattr(self, fn_name)
                for fn_name in dir(self) if fn_name.startswith("_CodStatusBot__cmd_") }
        #if updates_webhook is not None and not self._is_webhook_registered():
        #    self._register_webhook(updates_webhook)
        #self.cod_stats = CodStats(cod_user, cod_pwd)

    def updates_polling(self, timeout_s: int = 1):
        """
        Checks for updates every certain time set by `period_ms`.

        :param timeout_s: Seconds before the long polling timeout

        :raise Exception: Whether there is a problem communicating with the
         Telegram API
        """
        endpoint = f"{self.base_url}/getUpdates"
        headers = {"content-type": "application/json"}
        payload = {"timeout": timeout_s, "offset": self._update_offset}
        while True:
            payload["offset"] = self._update_offset
            response = self._call_endpoint("getUpdates", "POST", headers, payload)

            for update in response["result"]:
                self._process_update(update)
                if update["update_id"]+1 > self._update_offset:
                    self._update_offset = update["update_id"]+1
            time.sleep(timeout_s)

    def _process_update(self, update: dict):
        """
        Process the updates

        :param update: The update object. The format of the dictionary is defined
         here https://core.telegram.org/bots/api#update
        """
        # For the moment only bot_commands
        bot_command = ""
        bot_command_args = ""
        if not "message" in update:
            update["message"] = update["edited_message"]
        if not "text" in update["message"]:
            return
        for entity in update["message"]["entities"]:
            if entity["type"] == "bot_command":
                entity_from = entity["offset"]
                entity_to = entity_from + entity["length"]
                # Removing the first `/`
                bot_command = update["message"]["text"][entity_from:entity_to][1:]
                bot_command_args = update["message"]["text"][entity_to+1:].split(" ")
        if bot_command == "":
            return

        # This gonna divert the call to the correct __cmd_<command> function
        self.bot_command_fn.get(bot_command, self.bot_command_fn["default"])(bot_command_args, update)

    def _get_me(self) -> dict:
        """
        Gets the bot information

        :returns: Bot information. The format of the resulted dictionary
         is specified here https://core.telegram.org/bots/api#user
        """
        return self._call_endpoint("getWebhookInfo", "GET")
        
    def _send_message(self, chat_id: str, text: str):
        """
        Send the `text` message to the chat with id `chat_id`

        :param chat_id: The id of the chat where to send the message
        :param text: The text to send
        """
        endpoint = f"{self.base_url}/sendMessage"
        headers = {"content-type": "application/json"}
        payload = {"chat_id": chat_id, "text": text}
        try:
            self._call_endpoint("sendMessage", "POST", headers, payload)
        except Exception:
            print("WARNING: Message could not be sent")

    def _is_webhook_registered(self) -> bool:
        """
        Checks out whether there is any URL registered as webhook.
        
        :returns: True if there is any, false otherwise
        """
        r = self._call_endpoint("getWebhookInfo", "GET")
        return len(r["url"]) > 0

    def _register_webhook(self, webhook: str):
        """
        Register a webhook for the Telegram Bot
        """
        endpoint = f"{self.base_url}/setWebhook"
        headers = {"content-type": "application/json"}
        payload = {"url": webhook}
        self._call_endpoint("setWebhook", "POST", headers, payload)

    def _call_endpoint(self, endpoint: str, verb: str, headers: dict={}, payload: dict={}) -> dict:
        """
        Call to the endpoint and return the result

        :param endpoint: The endpoing to use
        :param verb: The verb to use, for the moment only implemented GET and POST
        :param headers: The headers to use in the request
        :param paylead: The data to send in the request
        :param paylead: The data to send in the request

        :return: The result of the request
        """
        requester = self.session.post if verb == "POST" else self.session.get
        r = requester(f"{self.base_url}/{endpoint}", 
                headers = headers, 
                data = json.dumps(payload))
        jr = json.loads(r.text)
        if "ok" in jr and jr["ok"] != True:
            raise Exception(f"Error processing the request to {endpoint} ERROR={jr['description']}")
        elif r.status_code != 200:
            raise Exception("Error communicating with the server")
        return jr

    def __cmd_start(self, args: list, update: dict):
        """
        Telegram is used to send `/start` whenever a bot is added into a group.
        This bot command just shows up a funny welcome message.

        :param args: The args are gonna be ignored.
        """
        chat_id = update["message"]["chat"]["id"]
        self._send_message(
                chat_id,
                "Hey there! I am the fucking bo(ss)t")

    def __cmd_cod_level(self, args: list, update: dict):
        """
        This bot command returns a message with the level information for a given player in a
        given platform.

        :param args: It must be a two value list
            - player: Is the player name
            - platform: Is the platform from where we want to take the information
        """

        chat_id = update["message"]["chat"]["id"]
        if len(args) != 2:
            self._send_message(chat_id, "Specify one player: /cod_level <player> <platform>")
            return
        player_name = args[0]
        player_platform = args[1]
        self._send_message(chat_id, f"Getting information from player {player_name}...")
        try:
            player_info = self.cod_stats.get_player_info(
                    player_name, 
                    player_platform
            )
            player_level = player_info["data"]["level"]
            self._send_message(chat_id, f"{player_name} has the level {player_level}!")
        except Exception:
            self._send_message(chat_id, f"Error getting info from the player {player_name}... :(")

    def __cmd_default(self, args: list, update: dict):
        """
        The default bot_command handler. DO NOT REMOVE THIS
        """
        chat_id = update["message"]["chat"]["id"]
        self._send_message(chat_id, "Don't know what you say. Take off the cock from your mouth")
