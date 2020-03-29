import logging
import threading
import PySimpleGUI as sg

import configuration as cfg
from chase_scraper import ChaseScraper

KEY_CHASE_USERNAME = "chase_username-key"
KEY_CHASE_PASSWORD = "chase_password-key"
KEY_CHASE_SIGNIN = "chase_signin-key"

FONT_TITLE = ("Gill Sans", 35)
FONT_TEXT = ("Gill Sans Light", 16)

sg.SetOptions(font=FONT_TEXT)

config = cfg.get_configuration()

# sg.preview_all_look_and_feel_themes()


class ScraperThread:
    scraper = None
    thread = None

    def get_scraper(self):
        if not self.scraper:
            self.scraper = ChaseScraper(config.chromedriver_path)
        return self.scraper

    def logon(self, username, password):
        self._run_in_thread(lambda: self.get_scraper().logon(username, password))

    def _run_in_thread(self, target):
        if self.thread and self.thread.is_alive():
            logging.error("thread already running")
            return
        self.thread = threading.Thread(target=target)
        self.thread.start()

    def quit(self, timeout=0):
        if self.scraper:
            self.scraper.quit(timeout)


# ------ Chase Frame Definition ------ #
sg.theme('DarkBlue15')
chase_frame = sg.Frame("Chase", font=FONT_TITLE, relief=sg.RELIEF_FLAT, layout=
[
    [
        sg.Text("Login: ", size=(15, 1), justification='right'),
        sg.InputText(key=KEY_CHASE_USERNAME, default_text=config.chase_username)
    ],
    [
        sg.Text("Password: ", size=(15, 1), justification='right'),
        sg.InputText(key=KEY_CHASE_PASSWORD, password_char='*')]
    ,
    [
        sg.Button("Sign In", key=KEY_CHASE_SIGNIN)
    ]
])


def handle_chase_events(event, values):
    if event == KEY_CHASE_SIGNIN:
        scraper_thread.logon(values[KEY_CHASE_USERNAME], values[KEY_CHASE_PASSWORD])


# ------ Google Sheets Frame Definition ------ #
sg.ChangeLookAndFeel('DarkAmber')
gsheets_frame = sg.Frame("Sheets", font=FONT_TITLE, relief=sg.RELIEF_FLAT, layout=
[
    [sg.Text("Sheets contents", justification='center')]
])

layout = [
    [
        chase_frame,
        gsheets_frame
    ],
    [
        sg.Button('Exit', )
    ]
]

window = sg.Window("Chazeets", layout, keep_on_top=True)

scraper_thread = ScraperThread()
while True:
    event, values = window.read(timeout=100)
    if event in (None, 'Exit'):
        break
    window.Reappear()
    handle_chase_events(event, values)

window.close()
scraper_thread.quit(0)
