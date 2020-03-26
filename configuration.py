import os
import json
import logging

CONFIG_FILE_DEFAULT = "./config-default.json"
CONFIG_FILE_PERSO = "./config.json"


class Configuration:
    # make it a singleton
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Configuration, cls).__new__(cls)
        return cls._instance

    chromedriver_path = None
    chase_accounts = []
    _loaded = False

    def load(self, config_file_path=CONFIG_FILE_DEFAULT):
        if not os.path.exists(config_file_path):
            logging.warning(f"{config_file_path} does not exist")
            return

        with open(config_file_path, 'r') as f:
            contents = json.load(f)
            for key in contents:
                self.__dict__[key] = contents[key]
        self._loaded = True


def get_configuration():
    config = Configuration()
    if not config._loaded:
        config.load(CONFIG_FILE_DEFAULT)
        config.load(CONFIG_FILE_PERSO)
    return config


if __name__ == '__main__':
    configuration = get_configuration()
    print(configuration.chromedriver_path)
    print(configuration.chase_accounts)

