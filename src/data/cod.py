import requests
import json
import re

from typing import List

class CodStats(object):
    def __init__(self, user, password):
        self.user = user
        self.password = password

        self.session = requests.Session()
        self._csrf_token = self._get_csrf_token()
        self._login(user, password)

    def get_player_info(self, player: str, platform: str = "psn"):
        """
        Get all the player information for the player with name `player`

        :returns: A dictionary with the format described in 
         https://documenter.getpostman.com/view/7896975/SW7aXSo5?version=latest#91d461fa-6851-432d-afa8-beb3404bd871
        """
        endpoint = f"https://my.callofduty.com/api/papi-client/stats/cod/v1/title/mw/platform/{platform}/gamer/{player}/profile/type/mp"
        r = self.session.get(endpoint)
        if r.status_code != 200:
            raise Exception(f"Error communicating with the API: {r.text}")
        return json.loads(r.text)

    def get_feed(self, from_epoch: int) -> List[dict]:
        endpoint = "https://my.callofduty.com/api/papi-client/userfeed/v1/friendFeed/"
        r = self.session.get(endpoint)
        if r.status_code != 200:
            raise Exception(f"Error communicating with the API: {r.text}")
        jr = json.loads(r.text)
        return [event for event in jr["data"]["events"] if event["date"] > from_epoch]


    def _get_csrf_token(self):
        """
        Gets the CSRF token from the login page form according with the
        documentation here https://documenter.getpostman.com/view/7896975/SW7aXSo5?version=latest#45160863-76eb-4347-87f1-2473f6477a0e

        :raise Exception: When there is any error loading the loging page
        """

        r = self.session.get("https://profile.callofduty.com/cod/login")
        if r.status_code != 200:
            raise Exception(f"Error accessing COD login page: {r.status_code}")
        return re.search("name=\"_csrf\" content=\"(.*)\"", r.text)[1]

    def _login(self, user: str, password: str):
        form = {
            "username": f"{user}",
            "password": f"{password}",
            "remember_me": "true",
            "_csrf": f"{self._csrf_token}"
        }

        r = self.session.post(
                "https://profile.callofduty.com/do_login?new_SiteId=cod",
                data = form)

        # TODO Check out whether the token named `atkn` exists in self.session.cookies
        # to have knowledge of whether the login has been successfully or not

        if r.status_code != 200:
            raise Exception(f"Error logging to the COD platform: {r.text}")
        else:
            print("Successfully logged in into COD platform")
