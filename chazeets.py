import datetime as dt
import logging
import threading
import PySimpleGUI as sg

import configuration as cfg
from chase_scraper import ChaseScraper

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


class ScraperThread:
    scraper = None
    thread = None

    def __init__(self, config):
        self.config = config

    def get_scraper(self):
        if not self.scraper:
            self.scraper = ChaseScraper(self.config.chromedriver_path)
        return self.scraper

    def logon(self, username, password):
        self._run_in_thread(lambda: self.get_scraper().logon(username, password))

    def _run_in_thread(self, target):
        if self.thread and self.thread.is_alive():
            logging.error("thread already running")
            return
        self.thread = threading.Thread(target=target)
        self.thread.start()

    def close(self, timeout=0):
        if self.scraper:
            self.scraper.quit(timeout)


def main():
    config = cfg.get_configuration()

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
    [[sg.Checkbox(account, key=account_key(account), default=True)] for account in config.chase_accounts])

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

    layout = [
        [date_range_frame],
        [chase_frame, sg.VerticalSeparator(), gsheets_frame],
        [sg.Button('Run', key=KEY_RUN, size=(20, 1)), sg.Text("", size=(80, 1)), sg.Button('Exit')]
    ]

    window = sg.Window("Chazeets", layout, keep_on_top=True, element_justification='center')


    scraper_thread = ScraperThread(config)
    while True:
        event, values = window.read(timeout=100)
        if event == '__TIMEOUT__':
            continue
        if event in (None, 'Exit'):
            break
        if event == KEY_CHASE_SIGNIN:
            scraper_thread.logon(values[KEY_CHASE_USERNAME], values[KEY_CHASE_PASSWORD])
        if event == KEY_RUN:
            pass
            #scraper_thread.logon(values[KEY_CHASE_USERNAME], values[KEY_CHASE_PASSWORD])

    window.close()
    scraper_thread.close(0)


if __name__ == "__main__":
    main()


