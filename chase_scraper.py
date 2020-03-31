import time
import argparse
import logging
from selenium import webdriver

import configuration as cfg

# need to hack chrome driver to avoid bot detection
# https://stackoverflow.com/questions/33225947/can-a-website-detect-when-you-are-using-selenium-with-chromedriver/41904453#41904453


DEFAULT_DRIVER_PATH = './chromedriver'

CHASE_LOGIN_URL = "https://secure01b.chase.com/web/auth"
CHASE_STATEMENTS_URL = "https://secure01b.chase.com/web/auth/dashboard#/dashboard/accountServicing/downloadAccountTransactions/index;params="

INPUT_LOGON_USERNAME_ID = 'userId-text-input-field'
INPUT_LOGON_PASSWORD_ID = 'password-text-input-field'

DROPDOWN_ACTIVITY_XPATH = "/html/body/div[2]/div/div[1]/div[2]/main/div[3]/div/div/div[2]/div/div[2]/div/div[2]/div/div[2]/div/div"
DROPDOWN_DATE_RANGE_XPATH = '//text()[. = "Choose a date range"]/../..'

INPUT_DATE_FROM_ID = 'input-accountActivityFromDate-validate-input-field'
INPUT_DATE_TO_ID = 'input-accountActivityToDate-validate-input-field'
BUTTON_DOWNLOAD_ID = 'download'
BUTTON_DOWNLOAD_OTHER_ID = 'downloadOtherActivity'

DATE_FORMAT = '%m/%d/%Y'


class ChaseScraper:
    def __init__(self, driver_path=DEFAULT_DRIVER_PATH):
        options = webdriver.ChromeOptions()
        options.add_argument("--disable-extensions")
        self.driver = webdriver.Chrome(options=options, executable_path=driver_path)

    def logon(self, username, password, wait_seconds=3):
        self.driver.get(CHASE_LOGIN_URL)
        self._find_by_id(INPUT_LOGON_USERNAME_ID).send_keys(username)
        self._find_by_id(INPUT_LOGON_PASSWORD_ID).send_keys(password)
        self._find_by_id(INPUT_LOGON_PASSWORD_ID).submit()
        time.sleep(wait_seconds)

    def quit(self, wait_seconds=5):
        time.sleep(wait_seconds)   # give time to finish last action
        if self.driver:
            self.driver.quit()
            self.driver = None

    def download_statement(self, account_id, date_from, date_to):
        logging.info(f"Retrieving statement for account {account_id} from {date_from} to {date_to}")
        self.driver.get(CHASE_STATEMENTS_URL + account_id)
        time.sleep(1)

        activity_element = self._find_by_xpath(DROPDOWN_ACTIVITY_XPATH)
        activity_element.click()
        time.sleep(.5)

        date_link_element = self._find_by_xpath(DROPDOWN_DATE_RANGE_XPATH)
        date_link_element.click()

        self._find_by_id(INPUT_DATE_FROM_ID).send_keys(date_from)
        self._find_by_id(INPUT_DATE_TO_ID).send_keys(date_to)

        self._find_by_id(BUTTON_DOWNLOAD_ID).click()
        self._find_by_id(BUTTON_DOWNLOAD_OTHER_ID).click()
        time.sleep(1)

    def _find_by_id(self, elt_id, timeout_s=10):
        return self._find(self.driver.find_element_by_id, [elt_id], timeout_s)

    def _find_by_ids(self, elt_id_list, timeout_s=10):
        return self._find(self.driver.find_element_by_id, elt_id_list, timeout_s)

    def _find_by_xpath(self, xpath, timeout_s=10):
        return self._find(self.driver.find_element_by_xpath, [xpath], timeout_s)

    @staticmethod
    def _find(finder, elt_id_list, timeout_s):
        max_time = time.time() + timeout_s
        item = None
        while not item and time.time() < max_time:
            for elt_id in elt_id_list:
                try:
                    item = finder(elt_id)
                except Exception as e:
                    pass
            if not item:
                time.sleep(.5)
        if not item:
            logging.error(f"Could not find item(s) {elt_id_list}")
        return item


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--username')
    parser.add_argument('-p', '--password')
    args = parser.parse_args()

    username_ = args.username if args.username else input("username: ")
    password_ = args.password if args.password else input("password: ")

    config = cfg.get_configuration()

    scraper = ChaseScraper(config.chromedriver_path)
    scraper.logon(username_, password_)

    for name, account in config.chase_accounts.items():
        scraper.download_statement(account, '01/01/2020', '01/31/2020')

    scraper.quit()
