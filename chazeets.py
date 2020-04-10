import datetime as dt
import logging
import threading
import time
import collections
import PySimpleGUI as sg

import configuration as cfg
from chase_scraper import ChaseScraper
from chase_scraper import DATE_FORMAT as CHASE_DATE_FORMAT

KEY_DATES_FROM = "date_from-key"
KEY_DATES_TO = "date_to-key"

KEY_CHASE_USERNAME = "chase_username-key"
KEY_CHASE_PASSWORD = "chase_password-key"
KEY_CHASE_SIGNIN = "chase_button_signin-key"

KEY_RUN = "button_run-key"

FONT_TITLE = ("Gill Sans Bold", 35)
FONT_GROUP = ("Gill Sans", 25)
FONT_TEXT = ("Gill Sans Light", 16)

FORMAT_DATE = "%Y-%m-%d"


class BackgroundWorker:
    scraper = None
    thread = None
    queue = collections.deque()
    exit = False

    def __init__(self):
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while not self.exit:
            if self.queue:
                (action, args) = self.queue.popleft()
                try:
                    action(*args)
                except Exception as e:
                    logging.error(e)

            else:
                time.sleep(.1)

    def enqueue(self, action, *args):
        self.queue.append((action, args))


class ChaseScraperWrapper:
    scraper = None

    def __init__(self, config: cfg.Configuration):
        self.config = config

    def get_scraper(self):
        if not self.scraper:
            self.scraper = ChaseScraper(self.config.chromedriver_path)
        return self.scraper

    def logon(self, username, password):
        self.get_scraper().logon(username, password)

    def download_statement(self, account_id, date_from, date_to):
        self.get_scraper().download_statement(account_id, date_from, date_to)

    def close(self, timeout=0):
        if self.scraper:
            self.scraper.quit(timeout)
            self.scraper = None


def login_only(worker: BackgroundWorker, scraper: ChaseScraperWrapper, username, password):
    worker.enqueue(scraper.logon, username, password)


def run_all(worker: BackgroundWorker, scraper: ChaseScraperWrapper, username, password, accounts, date_from, date_to):
    chase_date_from = dt.datetime.strptime(date_from, FORMAT_DATE).strftime(CHASE_DATE_FORMAT)
    chase_date_to = dt.datetime.strptime(date_to, FORMAT_DATE).strftime(CHASE_DATE_FORMAT)
    worker.enqueue(scraper.logon, username, password)
    for account in accounts:
        worker.enqueue(scraper.download_statement, account, chase_date_from, chase_date_to)
    worker.enqueue(scraper.close, 5)


def main():
    config = cfg.get_configuration()
    chase_scraper = ChaseScraperWrapper(config)
    background_worker = BackgroundWorker()

    now = dt.datetime.now()
    first_day_of_this_month = dt.datetime(now.year, now.month, 1)
    date_to = first_day_of_this_month - dt.timedelta(days=1)
    date_from = dt.datetime(date_to.year, date_to.month, 1)

    sg.SetOptions(font=FONT_TEXT)

    # ------ Date Range Definition ------ #
    sg.theme('DarkTeal7')
    date_range_frame = sg.Frame("", relief=sg.RELIEF_FLAT, element_justification='left', layout=
    [
        [sg.Text("From:"),
         sg.InputText(key=KEY_DATES_FROM, size=(10, 1), justification='center',
                      default_text=date_from.strftime(FORMAT_DATE)),
         sg.CalendarButton("Pick", target=KEY_DATES_FROM, format=FORMAT_DATE),
         sg.Text("", size=(3, 1)),
         sg.Text("To:"),
         sg.InputText(key=KEY_DATES_TO, size=(10, 1), justification='center', default_text=date_to.strftime(FORMAT_DATE)),
         sg.CalendarButton("Pick", target=KEY_DATES_TO, format=FORMAT_DATE)]
    ])

    # ------ Chase Frame Definition ------ #
    sg.theme('DarkBlue15')
    chase_logon_frame = sg.Frame("Logon", font=FONT_GROUP, relief=sg.RELIEF_RIDGE, layout=
    [
        [
            sg.Text("Login: ", size=(15, 1), justification='right'),
            sg.InputText(key=KEY_CHASE_USERNAME, size=(20, 1), justification='center', default_text=config.chase_username)
        ],
        [
            sg.Text("Password: ", size=(15, 1), justification='right'),
            sg.InputText(key=KEY_CHASE_PASSWORD, size=(20, 1), justification='center', password_char='*')
        ],
        [
            sg.Text("", size=(25, 1)), sg.Button("Sign In only", key=KEY_CHASE_SIGNIN)
        ]
    ])

    def account_key(account):
        return f"account_{account}-key"

    chase_accounts_frame = sg.Frame("Accounts", font=FONT_GROUP, relief=sg.RELIEF_RIDGE, layout=
    [[sg.Checkbox(account, key=account_key(key), default=True)] for key, account in config.chase_accounts.items()])

    chase_frame = sg.Frame("Chase", font=FONT_TITLE, relief=sg.RELIEF_FLAT, layout=
    [
        [chase_logon_frame],
        [chase_accounts_frame]
    ])

    # ------ Google Sheets Frame Definition ------ #
    sg.ChangeLookAndFeel('DarkAmber')
    gsheets_frame = sg.Frame("Sheets", font=FONT_TITLE, relief=sg.RELIEF_FLAT, layout=
    [
        [sg.Text("Sheets contents", justification='center')]
    ])

    # ------ XPath Frame Definition ------ #
    sg.ChangeLookAndFeel('DarkAmber')
    xpath_frame = sg.Frame("XPath Tester", font=FONT_GROUP, relief=sg.RELIEF_FLAT, layout=
    [
        [sg.T("XPATH:"), sg.In(key="XPATH")],
        [sg.Button(button_text="Go", key='XP_FIND'), sg.Button(button_text="Click", key='XP_CLICK')]
    ])

    layout = [
        [date_range_frame],
        [chase_frame, sg.VerticalSeparator(), sg.Column([[gsheets_frame], [xpath_frame]])],
        [sg.Button('Run', key=KEY_RUN, size=(20, 1)), sg.Text("", size=(15, 1)), sg.Button('Exit')]
    ]

    window = sg.Window("Chazeets", layout, keep_on_top=True, element_justification='center')

    while True:
        event, values = window.read(timeout=100)
        if event == '__TIMEOUT__':
            continue
        if event in (None, 'Exit'):
            break
        if event == KEY_CHASE_SIGNIN:
            login_only(background_worker, chase_scraper, values[KEY_CHASE_USERNAME], values[KEY_CHASE_PASSWORD])
        if event == KEY_RUN:
            selected_accounts = [config.chase_accounts[account] for account in config.chase_accounts if values[account_key(account)]]
            run_all(background_worker, chase_scraper, values[KEY_CHASE_USERNAME], values[KEY_CHASE_PASSWORD], selected_accounts, values[KEY_DATES_FROM], values[KEY_DATES_TO])
        if event in ("XP_FIND", "XP_CLICK"):
            elt = chase_scraper.scraper._find_by_xpath(values['XPATH'], 1)
            print(elt)
            if event == "XP_CLICK":
                elt.click()
    window.close()
    chase_scraper.close(0)


if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    main()


