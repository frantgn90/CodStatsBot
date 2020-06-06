import os
import argparse
from src.cod_status_bot import CodStatusBot

# Do not share this! If you do so, whomever could access the bot API
TELEGRAM_BOT_TOKEN = "1280124708:AAGDbhllaGo261mk0JJ__musRqMPtTjEUKE"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Call of Duty stats Telegram bot")
    parser.add_argument(
        "--cod_user", required=True, type=str, help="The COD platform user"
    )
    parser.add_argument(
        "--cod_pass", required=True, type=str, help="The COD platform user"
    )
    parser.add_argument(
        "--updates_timeout_s",
        type=int,
        help="Timeout for taking updates from telegram",
        required=False,
        default=3,
    )
    args = parser.parse_args()

    # For the moment we are not gonna set the webhook since this is not running on a
    # machine with a static public IP nor domain. Even though this is desirable since
    # it provides better CPU usage. Instead of being polling, just listen for requests.
    # My guess is that the fastAPI library would be a nice choice.

    cod_status_bot = CodStatusBot(TELEGRAM_BOT_TOKEN, args.cod_user, args.cod_pass)
    cod_status_bot.updates_polling(timeout_s=args.updates_timeout_s)
