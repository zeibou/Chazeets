import datetime as dt
import logging
import threading
import time
import collections
import PySimpleGUI as sg

import configuration as cfg
from chase_scraper import ChaseScraper
from chase_scraper import DATE_FORMAT as CHASE_DATE_FORMAT
from sheet_uploader import SheetUploader
import splitwise_uploader as splitwise

KEY_DATES_FROM = "date_from-key"
KEY_DATES_TO = "date_to-key"
KEY_MONTH_PREV = "button_month_prev-key"
KEY_MONTH_NEXT = "button_month_next-key"

KEY_CHASE_USERNAME = "chase_username-key"
KEY_CHASE_PASSWORD = "chase_password-key"

KEY_SIGNIN = "button_signin-key"
KEY_RUN = "button_run_key"
KEY_PUSH = "button_push-key"
KEY_RUN_ALL = "button_runall-key"

KEY_SHEET_TABS = "choice_tabs-key"
KEY_SHEET_REFRESH = "button_sheet_refresh-key"
KEY_SHEET_CONTENT = "txt_sheet_content-key"
KEY_SPLITWISE_PUSH = "button_splitwise_push-key"


FONT_TITLE = ("Gill Sans Bold", 35)
FONT_GROUP = ("Gill Sans", 25)
FONT_TEXT = ("Gill Sans Light", 16)
FONT_TEXT2 = ("Arial", 16)

FORMAT_DATE = "%Y-%m-%d"

SELECT_STR = " <select> "

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


def login(worker: BackgroundWorker, scraper: ChaseScraperWrapper, username, password):
    worker.enqueue(scraper.logon, username, password)


def get_statements(worker: BackgroundWorker, scraper: ChaseScraperWrapper, accounts, date_from, date_to):
    chase_date_from = dt.datetime.strptime(date_from, FORMAT_DATE).strftime(CHASE_DATE_FORMAT)
    chase_date_to = dt.datetime.strptime(date_to, FORMAT_DATE).strftime(CHASE_DATE_FORMAT)
    for account in accounts:
        worker.enqueue(scraper.download_statement, account, chase_date_from, chase_date_to)
    worker.enqueue(scraper.close, 5)


def upload_to_sheets(worker: BackgroundWorker, sheet_uploader: SheetUploader, date_from_str, date_to_str):
    chase_date_from = dt.datetime.strptime(date_from_str, FORMAT_DATE)
    chase_date_to = dt.datetime.strptime(date_to_str, FORMAT_DATE)
    worker.enqueue(sheet_uploader.upload_statements, chase_date_from, chase_date_to, dt.datetime.today())


def get_sheet_tabs(sheet_uploader: SheetUploader):
    return [SELECT_STR] + [w.title for w in sheet_uploader.api.sheet.worksheets()]


def main():
    config = cfg.get_configuration()
    chase_scraper = ChaseScraperWrapper(config)
    sheet_uploader = SheetUploader(config)
    sw = splitwise.init(config)
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
        [sg.Button(" << ", key=KEY_MONTH_PREV),
         sg.Text("From:"),
         sg.InputText(key=KEY_DATES_FROM, size=(10, 1), justification='center',
                      default_text=date_from.strftime(FORMAT_DATE)),
         sg.CalendarButton("Pick", target=KEY_DATES_FROM, format=FORMAT_DATE),
         sg.Text("", size=(3, 1)),
         sg.Text("To:"),
         sg.InputText(key=KEY_DATES_TO, size=(10, 1), justification='center', default_text=date_to.strftime(FORMAT_DATE)),
         sg.CalendarButton("Pick", target=KEY_DATES_TO, format=FORMAT_DATE),
         sg.Button(" >> ", key=KEY_MONTH_NEXT)]
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
        ]
    ])

    def account_key(account):
        return f"account_{account}-key"

    chase_accounts_frame = sg.Frame("Accounts", font=FONT_GROUP, relief=sg.RELIEF_RIDGE, layout=
    [[sg.Checkbox(account, key=account_key(key), default=True)] for key, account in config.chase_accounts.items()])

    chase_frame = sg.Frame("Chase", font=FONT_TITLE, relief=sg.RELIEF_FLAT, layout=
    [
        [chase_logon_frame],
        [chase_accounts_frame,
                   sg.Column([[sg.Text('')],
                              [sg.Button("Sign In", key=KEY_SIGNIN, size=(20, 1))],
                              [sg.Button('Download Statements', key=KEY_RUN, size=(20, 1))],
                              [sg.Button('Export to Sheets', key=KEY_PUSH, size=(20, 1))]])],
        [sg.Button("Chase -> Sheets", size=(40, 1), key=KEY_RUN_ALL)]
    ])

    # ------ Google Sheets Frame Definition ------ #
    sg.ChangeLookAndFeel('DarkAmber')
    gsheets_frame = sg.Frame("Sheets - Splitwise", font=FONT_TITLE, relief=sg.RELIEF_FLAT, layout=
    [
        [sg.InputOptionMenu(values=get_sheet_tabs(sheet_uploader), key=KEY_SHEET_TABS, text_color='black'), sg.Button("Refresh", key=KEY_SHEET_REFRESH)],
        [sg.Multiline(size=(30, 10), font=FONT_TEXT2, key=KEY_SHEET_CONTENT)],
        [sg.Button(f"Upload to {sw.getGroup(config.splitwise_group_id).name}", size=(30, 1), key=KEY_SPLITWISE_PUSH)]
    ])

    # ------ XPath Frame Definition ------ #
    # sg.ChangeLookAndFeel('DarkAmber')
    # xpath_frame = sg.Frame("XPath Tester", font=FONT_GROUP, relief=sg.RELIEF_FLAT, layout=
    # [
    #     [sg.T("XPATH:"), sg.In(key="XPATH")],
    #     [sg.Button(button_text="Go", key='XP_FIND'), sg.Button(button_text="Click", key='XP_CLICK')]
    # ])

    layout = [
        [date_range_frame],
        [chase_frame, sg.VerticalSeparator(), gsheets_frame],
        #[chase_frame, sg.VerticalSeparator(), sg.Column([[gsheets_frame], [xpath_frame]])],
       # [sg.Text("", size=(45, 1)), sg.Button('Exit')]
    ]

    window = sg.Window("Chazeets", layout, keep_on_top=True, element_justification='center')
    curr_tab = SELECT_STR
    while True:
        event, values = window.read(timeout=100)
        if event == '__TIMEOUT__':
            if values[KEY_SHEET_TABS] != curr_tab:
                curr_tab = values[KEY_SHEET_TABS]
                if curr_tab == SELECT_STR:
                    window[KEY_SHEET_CONTENT].update(value="")
                else:
                    expenses = '\n'.join([str(e) for e in sheet_uploader.pull_totals(curr_tab)])
                    window[KEY_SHEET_CONTENT].update(value=expenses)
            continue
        if event in (None, 'Exit'):
            break
        if event == KEY_MONTH_PREV:
            curr_df = dt.datetime.strptime(values[KEY_DATES_FROM], FORMAT_DATE)
            first_day_of_curr_month = dt.datetime(curr_df.year, curr_df.month, 1)
            date_to = first_day_of_curr_month - dt.timedelta(days=1)
            date_from = dt.datetime(date_to.year, date_to.month, 1)
            window[KEY_DATES_FROM].update(value=date_from.strftime(FORMAT_DATE))
            window[KEY_DATES_TO].update(value=date_to.strftime(FORMAT_DATE))
        if event == KEY_MONTH_NEXT:
            curr_df = dt.datetime.strptime(values[KEY_DATES_TO], FORMAT_DATE) + dt.timedelta(days=1)
            date_from = dt.datetime(curr_df.year, curr_df.month, 1)
            date_to = date_from + dt.timedelta(days=32)
            date_to = dt.datetime(date_to.year, date_to.month, 1) - dt.timedelta(days=1)
            window[KEY_DATES_FROM].update(value=date_from.strftime(FORMAT_DATE))
            window[KEY_DATES_TO].update(value=date_to.strftime(FORMAT_DATE))
        if event == KEY_SIGNIN:
            login(background_worker, chase_scraper, values[KEY_CHASE_USERNAME], values[KEY_CHASE_PASSWORD])
        if event == KEY_RUN:
            selected_accounts = [config.chase_accounts[account] for account in config.chase_accounts if values[account_key(account)]]
            get_statements(background_worker, chase_scraper, selected_accounts, values[KEY_DATES_FROM], values[KEY_DATES_TO])
        if event == KEY_PUSH:
            upload_to_sheets(background_worker, sheet_uploader, values[KEY_DATES_FROM], values[KEY_DATES_TO])
        if event == KEY_RUN_ALL:
            login(background_worker, chase_scraper, values[KEY_CHASE_USERNAME], values[KEY_CHASE_PASSWORD])
            selected_accounts = [config.chase_accounts[account] for account in config.chase_accounts if values[account_key(account)]]
            get_statements(background_worker, chase_scraper, selected_accounts, values[KEY_DATES_FROM], values[KEY_DATES_TO])
            upload_to_sheets(background_worker, sheet_uploader, values[KEY_DATES_FROM], values[KEY_DATES_TO])
        if event == KEY_SHEET_REFRESH:
            sheet_uploader.api.refresh()
            window[KEY_SHEET_TABS].update(values=get_sheet_tabs(sheet_uploader))
        if event == KEY_SPLITWISE_PUSH:
            for e in sheet_uploader.pull_totals(curr_tab):
                splitwise.share_expense_with_group_members(sw, f"{curr_tab} - {e.item}", e.total, config.splitwise_group_id, date_to)
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


