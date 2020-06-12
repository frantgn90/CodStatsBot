import json
import time
import requests
from typing import List


class TelegramBot(object):
    """
    Basic implementation for a telegram bot. This class handles the updates to the but by pooling the updates endpoint
    and diverting the command to the proper handler function.

    In order to add a new command, the class that inherits
    from this one, should implement the methods with the name following the format: _cmd_<command>
    Additionally in handlers recurrent asynchronous events like new feeds. In order to introduce a new feed-like
    functionality you should implement methods with the name following the format _loop_<feed_name>. It will provide to
    the user the command /activate_<feed_name> yes|no
    """

    def __init__(self, telegram_bot_token: str):
        """
        Initialization of the telegram bot. It initialize all the needed data structures.

        :param telegram_bot_token: The Telegram Bot token
        """
        self.telegram_bot_token = telegram_bot_token
        self.base_url = f"https://api.telegram.org/bot{self.telegram_bot_token}"
        self.session = requests.Session()  # This is not strictly necessary

        self.me = self._get_me()

        # Register the bot whether it is specified
        # if updates_webhook is not None and not self._is_webhook_registered():
        #     self._register_webhook(updates_webhook)

        # All methods that handles the bot_commands. These methods are gonna be called
        # Automatically, you just need to name it in the next manner:
        #   __cmd_<command_text>
        self.bot_command_fn = {
            fn_name.replace("_cmd_", ""): getattr(self, fn_name)
            for fn_name in dir(self)
            if fn_name.startswith("_cmd_")
        }

        # All methods that should be called in the main loop.
        # Additionally this class provides the dictionary self.last_time and self.receive_feeds_in_chat_id
        self.bot_loop_fn = {
            fn_name.replace("_loop_", ""): getattr(self, fn_name)
            for fn_name in dir(self)
            if fn_name.startswith("_loop_")
        }
        self.last_time = {
            fn_name: int(time.time() * 1000) for fn_name in self.bot_loop_fn.keys()
        }
        self.receive_feeds_in_chat_id = {
            fn_name: None for fn_name in self.bot_loop_fn.keys()
        }

    def _send_message(self, chat_id: str, text: str):
        """
        Send the `text` message to the chat with id `chat_id`

        :param chat_id: The id of the chat where to send the message
        :param text: The text to send
        """
        headers = {"content-type": "application/json"}
        payload = {"chat_id": chat_id, "text": text}
        try:
            self._call_endpoint("sendMessage", "POST", headers, payload)
        except Exception:
            print("WARNING: Message could not be sent")

    def _call_endpoint(
        self, endpoint: str, verb: str, headers: dict = None, payload: dict = None
    ) -> dict:
        """
        Call to the endpoint and return the result

        :param endpoint: The endpoint to use
        :param verb: The verb to use, for the moment only implemented GET and POST
        :param headers: The headers to use in the request
        :param payload: The data to send in the request

        :return: The result of the request
        """
        requester = self.session.post if verb == "POST" else self.session.get
        r = requester(
            f"{self.base_url}/{endpoint}", headers=headers, data=json.dumps(payload)
        )
        jr = json.loads(r.text)
        if "ok" in jr and jr["ok"] is not True:
            raise Exception(
                f"Error processing the request to {endpoint} ERROR={jr['description']}"
            )
        elif r.status_code != 200:
            raise Exception("Error communicating with the server")
        return jr

    def _get_me(self) -> dict:
        """
        Gets the bot information

        :returns: Bot information. The format of the resulted dictionary
         is specified here https://core.telegram.org/bots/api#user
        """
        return self._call_endpoint("getWebhookInfo", "GET")

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
        headers = {"content-type": "application/json"}
        payload = {"url": webhook}
        self._call_endpoint("setWebhook", "POST", headers, payload)

    def process_loop(self):
        """
        Calls all the actions that must be performed continuously every
        certain amount of time. e.g. some polling on an endpoint
        """
        for fn_name, fn in self.bot_loop_fn.items():
            if self.receive_feeds_in_chat_id[fn_name] is not None:
                r = fn(self.last_time[fn_name], self.receive_feeds_in_chat_id[fn_name])
                if r:
                    self.last_time[fn_name] = int(time.time() * 1000)

    def process_update(self, update: dict):
        """
        Process the updates

        :param update: The update object. The format of the dictionary is defined
         here https://core.telegram.org/bots/api#update
        """
        if "message" not in update:  # e.g. when there is an edit_message
            print("Ignoring update: Not message in update")
            return
        if "text" not in update["message"]:
            print("Ignoring update: not text in message")
            return
        # Handle just plain text
        if "entities" not in update["message"]:
            print("Not entities in message. Handing as plain text")
            self._handle_text_message(update["message"]["text"], update)
            return

        for entity in update["message"]["entities"]:
            if entity["type"] == "bot_command":
                entity_from = entity["offset"]
                entity_to = entity_from + entity["length"]
                bot_command = update["message"]["text"][entity_from:entity_to][
                    1:
                ]  # Removing the first `/`
                bot_command_args = (
                    update["message"]["text"][entity_to + 1:].split(" ")
                    if len(update["message"]["text"][entity_to + 1:]) > 0
                    else []
                )

                # This gonna divert the call to the correct _cmd_<command> or __metacmd_<loop> function
                if bot_command in self.bot_command_fn:
                    self.bot_command_fn.get(bot_command)(bot_command_args, update)
                elif (
                    bot_command.startswith("activate_")
                    and bot_command.replace("activate_", "") in self.bot_loop_fn
                ):
                    self.__metacmd_activate_feed(
                        bot_command_args, bot_command.replace("activate_", ""), update
                    )
                else:
                    self.bot_command_fn["default"](bot_command_args, update)

    def _cmd_default(self, args: list, update: dict):
        """
        The default bot_command handler. DO NOT REMOVE THIS
        """
        chat_id = update["message"]["chat"]["id"]
        self._send_message(
            chat_id, "Don't know what you say. If you need help, type /help"
        )

    def __metacmd_activate_feed(self, args: List[str], feed_name: str, update: dict):
        """
        This method handles the activation/deactivation of the feeds on a given chat

        :param args: The arguments of the activate/deactivate feed command
        :param feed_name: The name of the feed
        :param update: The whole update information
        """
        chat_id = update["message"]["chat"]["id"]
        if len(args) != 1:
            self._send_message(chat_id, f"Usage: /{feed_name} [yes|no]")
            return
        if args[0] == "yes":
            self.receive_feeds_in_chat_id[feed_name] = chat_id
            self._send_message(chat_id, f"Congrats! {feed_name} activated")
        else:
            self.receive_feeds_in_chat_id[feed_name] = None
            self._send_message(
                chat_id, f"{feed_name} has been deactivated successfully"
            )

    def _handle_text_message(self, message: dict, update: dict) -> None:
        """
        Handles all the text messages. The default implementation does nothing at all

        :param message: The received message
        :param update:  The whole update object
        """
        pass
