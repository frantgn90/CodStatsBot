import secrets


class Account(object):
    account_id = None
    cod_user = None
    cod_password = None
    cod_platform = None
    secret_token = None

    def __init__(self, account_id):
        self.secret_token = secrets.token_hex(16)

    @classmethod
    def new_account(cls, cod_user: str, cod_password: str, chat_id: str):
        # TODO Insert data in database and return a new object referencing this data
        return cls("fake")

    @classmethod
    def get_account_by_token(cls, token: str):
        pass


class Accounts(object):
    """
    This class is devoted to manage a set of accounts
    """
    _accounts = []

    def __init__(self):
        pass

    def get_bot_account_from_chat_id(self, chat_id: str):
        """
        Returns the account_id whether the chat_id is related with an account. None otherwise

        :param chat_id: Chat id related to an account
        :return the account whether the relation exists, None otherwise:
        """
        return Account("fake")

    def get_feeds_activated_accounts(self) -> list:
        """
        This method returns all the accounts that have some feed activated.

        :return: Returns a list of accounts that have some feeds activated.
        """
        return []
