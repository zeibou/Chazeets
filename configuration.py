import os
import json


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

    def load(self, config_file_path="./config.json", force=False):
        if self._loaded and not force:
            return
        if not os.path.exists(config_file_path):
            raise FileNotFoundError(f"{config_file_path} does not exist")

        with open(config_file_path, 'r') as f:
            contents = json.load(f)
            self.chromedriver_path = contents['chromedriver_path']
            self.chase_accounts = contents['accounts']

        self._loaded = True


if __name__ == '__main__':
    config = Configuration()
    config.load()
    print(config.chromedriver_path)
    print(config.chase_accounts)
    config2 = Configuration()
    print(config2.chromedriver_path)
    print(config2.chase_accounts)

