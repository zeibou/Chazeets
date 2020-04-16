import os
import json
import logging
from enum import Enum

CONFIG_FILE_DEFAULT = "./config-default.json"
CONFIG_FILE_PERSO = "./config.json"


class AccountType(Enum):
    Checking = 1
    CreditCard = 2


class Account:
    def __init__(self, name, dico):
        self.name = name
        self.alias = dico.get("alias", name)
        self.url_param = dico.get("url_param")
        self.account_type = AccountType[dico.get("account_type")]
        self.last_4_digits = dico.get("last_4_digits")

    def __str__(self):
        return f"{self.alias}-{self.last_4_digits}"

    def __repr__(self):
        return f"{self.alias}-{self.last_4_digits}: {self.url_param} {self.account_type}"


class Configuration:
    # make it a singleton
    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Configuration, cls).__new__(cls)
        return cls._instance

    chromedriver_path = None
    chase_accounts = []
    chase_username = ''
    google_credentials_path = None
    google_spreadsheet_id = None
    statements_download_dir = None
    splitwise_key: None
    splitwise_secret: None
    splitwise_access_token: None
    splitwise_group_id: None

    def load(self, config_file_path, override_only=False):
        if not os.path.exists(config_file_path):
            logging.warning(f"{config_file_path} does not exist")
            return

        with open(config_file_path, 'r') as f:
            contents = json.load(f)
            for key in contents:
                if override_only and key not in self.__dict__:
                    logging.warning(f"Ignoring '{key}' because it is not an expected configuration item")
                else:
                    if key == "chase_accounts":
                        self.__dict__[key] = {a: Account(a, contents[key][a]) for a in contents[key]}
                    else:
                        self.__dict__[key] = contents[key]
        self._loaded = True


def get_configuration():
    config = Configuration()
    if not config._loaded:
        config.load(CONFIG_FILE_DEFAULT)
        config.load(CONFIG_FILE_PERSO, override_only=True)
    return config


if __name__ == '__main__':
    configuration = get_configuration()
    print(configuration.chromedriver_path)
    print(configuration.chase_accounts)

