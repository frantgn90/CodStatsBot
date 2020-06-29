from typing import List, Optional

import datetime as datetime
import mysql.connector


class DbData:
    def __init__(self, *args, **kwargs):
        pass

    @classmethod
    def from_tuple(cls, data):
        return cls(*data)


class CodFriend(DbData):
    def __init__(self, telegram_group_id: int, cod_player_name: str, cod_player_platform: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.telegram_group_id = telegram_group_id
        self.cod_player_name = cod_player_name
        self.cod_player_platform = cod_player_platform


class TelegramGroup(DbData):
    def __init__(self, telegram_group_id: int, account_id: int, feeds: set, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.telegram_group_id = telegram_group_id
        self.account_id = account_id
        self.feeds = feeds

        self.cod_friends_repository = CodFriendsRepository()
        self.cod_friends = self.cod_friends_repository.get_cod_friends_from_group_id(self.telegram_group_id)

    def create_player_to_group(self, player_name, player_platform):
        self.cod_friends.append(self.cod_friends_repository.create(self.telegram_group_id, player_name, player_platform))


class Account(DbData):
    def __init__(self, account_id: int, cod_user: str, cod_password: str, telegram_chat_id: int,
                 creation_datetime: datetime, telegram_user_id: int, fake_account: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.account_id = account_id
        self.cod_user = cod_user
        self.cod_password = cod_password
        self.telegram_user_id = telegram_user_id
        self.telegram_chat_id = telegram_chat_id
        self.fake_account = fake_account
        self.creation_datetime = creation_datetime

        # TODO All this data could be retrieved with a single query by using LEFT JOINS
        self.telegram_group_repository = TelegramGroupRepository()
        self.telegram_groups = self.telegram_group_repository.get_telegram_groups_from_account_id(self.account_id)

    def create_telegram_group(self, chat_id):
        self.telegram_groups.append(self.telegram_group_repository.create(chat_id, self.account_id))

    def add_player_to_group(self, chat_id, player_name, player_platform):
        for telegram_group in self.telegram_groups:
            if telegram_group.telegram_group_id == chat_id:
                telegram_group.create_player_to_group(player_name, player_platform)
                return

    def get_cod_friends(self, chat_id):
        for telegram_group in self.telegram_groups:
            if telegram_group.telegram_group_id == chat_id:
                return telegram_group.cod_friends
        return []

    @classmethod
    def fake_account(cls, chat_id, user_id):
        return cls(chat_id, "", "", chat_id, datetime.datetime.now(), user_id, True)

    @classmethod
    def from_tuple(cls, data):
        return cls(*data, fake_account=False)


class DbRepository:
    def __init__(self):
        self.db = mysql.connector.connect(
            host="localhost",
            user="root",
            database="codstatusbot")


class CodFriendsRepository(DbRepository):
    def get_cod_friends_from_group_id(self, telegram_group_id: int) -> List[CodFriend]:
        cursor = self.db.cursor()
        cursor.execute(f"SELECT * FROM telegram_group_cod_friends WHERE telegram_group_id = {telegram_group_id}")
        cod_friends_result = cursor.fetchall()

        return [CodFriend.from_tuple(cod_friend_result) for cod_friend_result in cod_friends_result]

    def create(self, telegram_group_id, player_name, player_platform) -> CodFriend:
        cursor = self.db.cursor()
        sql = f"INSERT INTO telegram_group_cod_friends (telegram_group_id, cod_player_name, cod_player_platform) " \
              f"VALUES ({telegram_group_id}, '{player_name}', '{player_platform}')"
        print(sql)
        cursor.execute(sql)

        self.db.commit()
        return CodFriend(telegram_group_id, player_name, player_platform)


class TelegramGroupRepository(DbRepository):
    def get_telegram_groups_from_account_id(self, account_id: int) -> List[TelegramGroup]:
        cursor = self.db.cursor()
        cursor.execute(f"SELECT * FROM telegram_groups WHERE account_id = {account_id}")
        telegram_groups_data = cursor.fetchall()

        return [TelegramGroup.from_tuple(telegram_group_data) for telegram_group_data in telegram_groups_data]

    def create(self, group_id, account_id):
        cursor = self.db.cursor()
        sql = f"INSERT INTO telegram_groups (telegram_group_id, account_id) VALUES ({group_id}, {account_id})"
        print(sql)
        cursor.execute(sql)

        self.db.commit()
        return TelegramGroup(cursor.lastrowid, group_id, account_id, ())


class AccountRepository(DbRepository):
    """
    This class is devoted to manage a set of accounts
    """
    def create(self, cod_user: str, cod_password: str, telegram_chat_id: int, telegram_user_id: int) -> Account:
        cursor = self.db.cursor()
        sql = (f"INSERT INTO accounts (cod_user, cod_password, telegram_user_id, chat_id)"
               f" VALUES ('{cod_user}', '{cod_password}', {telegram_user_id}, {telegram_chat_id})")
        print(sql)
        cursor.execute(sql)

        self.db.commit()
        return Account(cursor.lastrowid, cod_user, cod_password, telegram_chat_id, datetime.datetime.now(), telegram_user_id)

    def get(self, account_id) -> Optional[Account]:
        cursor = self.db.cursor()
        cursor.execute(f"SELECT * FROM accounts WHERE id={account_id}")
        account_data = cursor.fetchone()

        if cursor.rowcount > 0:
            return Account.from_tuple(account_data)
        return None

    def get_bot_account_from_chat_id(self, chat_id: str) -> Optional[Account]:
        """
        Returns the account_id whether the chat_id is related with an account. None otherwise

        :param chat_id: Chat id related to an account
        :return the account whether the relation exists, None otherwise:
        """
        cursor = self.db.cursor()
        sql = (f"SELECT * FROM accounts WHERE chat_id={chat_id} "
               f"OR id=(SELECT account_id FROM telegram_groups WHERE telegram_group_id={chat_id})")
        print(sql)
        cursor.execute(sql)
        account_data = cursor.fetchone()
        if cursor.rowcount > 0:
            return Account.from_tuple(account_data)
        return None

    def get_bot_account_from_user_id(self, user_id: int) -> Optional[Account]:
        """
        Returns an account from a user_id

        :param user_id: The telegram id of the user that owns the account
        :return: The account object or None depending on whether the account for the user exists
        """
        cursor = self.db.cursor()
        sql = f"SELECT * FROM accounts WHERE telegram_user_id={user_id}"
        print(sql)
        cursor.execute(sql)
        account_data = cursor.fetchone()
        if cursor.rowcount > 0:
            return Account.from_tuple(account_data)
        return None

    def get_feeds_activated_accounts(self) -> List[Account]:
        """
        This method returns all the accounts that have some feed activated.

        :return: Returns a list of accounts that have some feeds activated.
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM accounts WHERE id IN "
                       "(SELECT account_id FROM telegram_groups WHERE feeds IS NOT NULL)")
        accounts_data = cursor.fetchall()

        return [Account.from_tuple(account_data) for account_data in accounts_data]
