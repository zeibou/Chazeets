import os
import abc
import datetime as dt
import pandas as pd
import pygsheets
import logging
import configuration as cfg
from configuration import AccountType

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

SHEET_TEMPLATE_NAME = "_TEMPLATE_"
SHEET_CATEGORY_COL = 9
SHEET_CATEGORY_ROW = 4

# Date	Item	category	price		share factor	price to share
DF_COL_ACCOUNT = "Account"
DF_COL_DATE = "Date"
DF_COL_ITEM = "Item"
DF_COL_CATEGORY = "Category"
DF_COL_PRICE = "Price"
DF_COL_FACTOR = "Share Factor"
DF_COL_PRICE_TO_SHARE = "Price to share"


class SheetManager:
    def __init__(self, sheet_id, credentials_json, scopes):
        self.client = pygsheets.authorize(client_secret=credentials_json, scopes=scopes)
        self.sheet = self.client.open_by_key(sheet_id)

    def refresh(self):
        self.sheet = self.client.open_by_key(self.sheet.id)

    def get_safe_new_sheet_name(self, wanted_name):
        curr_sheets = {s.title: s for s in self.sheet.worksheets()}
        safe_name = wanted_name
        while safe_name in curr_sheets:
            safe_name = f"{wanted_name}_{dt.datetime.now():%Y%m%d_%H%M%S}"
        return safe_name

    def safe_create_sheet(self, name):
        safe_name = self.get_safe_new_sheet_name(name)
        return self.sheet.add_worksheet(safe_name)

    def safe_duplicate_sheet(self, target_name, source_name):
        if not self.sheet_exists(source_name):
            raise ValueError(f"Can't duplicate sheet {source_name}: does not exist")
        safe_name = self.get_safe_new_sheet_name(target_name)
        source_sheet = self.sheet.worksheet_by_title(source_name)
        return self.sheet.add_worksheet(safe_name, src_worksheet=source_sheet)

    def sheet_exists(self, name):
        curr_sheets = {s.title: s for s in self.sheet.worksheets()}
        return name in curr_sheets

    def find_sheet_by_prefix(self, prefix):
        for s in self.sheet.worksheets():
            if s.title.startswith(prefix):
                return s
        return None

    def get_or_create_worksheet(self, name):
        curr_sheets = {s.title: s for s in self.sheet.worksheets()}
        ws = self.sheet.add_worksheet(name) if name not in curr_sheets else curr_sheets[name]
        return ws


class Statement:
    data: pd.DataFrame

    def __init__(self, account: cfg.Account, path: str):
        self.account = account
        self.path = path

    def load(self):
        if os.path.exists(self.path):
            self.data = pd.read_csv(filepath_or_buffer=self.path, index_col=False)
        else:
            logging.warning(f"could not find statement file for account {self.account}. File {self.path} does not exist")

    @abc.abstractmethod
    def get_as_dataframe(self):
        return None

    def _create_empty_dataframe(self, date_series, item_series, category_series, price_series):
        df = pd.DataFrame(columns=[DF_COL_DATE, DF_COL_ITEM, DF_COL_CATEGORY, DF_COL_PRICE])
        nb_rows = len(date_series)
        df[DF_COL_ACCOUNT] = pd.Series([str(self.account)] * nb_rows)
        df[DF_COL_DATE] = date_series
        df[DF_COL_ITEM] = item_series
        df[DF_COL_CATEGORY] = category_series
        df[DF_COL_PRICE] = price_series
        df[DF_COL_FACTOR] = pd.Series([0] * nb_rows)
        df[DF_COL_PRICE_TO_SHARE] = pd.Series(['=INDIRECT("R[0]C[-2]", FALSE) * INDIRECT("R[0]C[-1]",FALSE)'] * nb_rows)
        return df


class CheckingStatement(Statement):
    def get_as_dataframe(self):
        if self.data is None:
            return None
        df = self._create_empty_dataframe(
            self.data["Posting Date"],
            self.data["Description"],
            self.data["Type"].str.replace('_', ' ').str.lower(),
            self.data["Amount"] * -1)
        return df


class CreditCardStatement(Statement):
    def get_as_dataframe(self):
        if self.data is None:
            return None
        df = self._create_empty_dataframe(
            self.data["Transaction Date"],
            self.data["Description"],
            self.data["Category"],
            self.data["Amount"] * -1)
        return df


class ExpenseTotal:
    def __init__(self, item, value):
        self.item = item
        self.total = value

    def __str__(self):
        return f"${self.total} on {self.item}"


class SheetUploader:
    def __init__(self, config: cfg.Configuration):
        self.config = config
        self.api = SheetManager(config.google_spreadsheet_id, config.google_credentials_path, SCOPES)

    @staticmethod
    def sheet_name(date):
        return f"{date:%b %Y}"

    def upload_statements(self, date_from: dt.datetime, date_to: dt.datetime, today: dt.datetime):
        df = pd.DataFrame(columns=[DF_COL_ACCOUNT, DF_COL_DATE, DF_COL_ITEM, DF_COL_CATEGORY, DF_COL_PRICE, DF_COL_FACTOR, DF_COL_PRICE_TO_SHARE])
        for i, s in enumerate(self.enumerate_statements(today, date_from, date_to)):
            s.load()
            dff = s.get_as_dataframe()
            if dff is not None:
                df = df.append(dff)

        sheet = self.api.safe_duplicate_sheet(SheetUploader.sheet_name(date_from), SHEET_TEMPLATE_NAME)
        sheet.index = 0
        sheet.set_dataframe(df, (1, 1))

    def enumerate_statements(self, download_date, date_from, date_to):
        for account in self.config.chase_accounts.values():
            if account.account_type == AccountType.Checking:
                expected_filename = f"Chase{account.last_4_digits}_Activity_{download_date:%Y%m%d}.CSV"
                yield CheckingStatement(account, os.path.join(self.config.statements_download_dir, expected_filename))
            elif account.account_type == AccountType.CreditCard:
                expected_filename = f"Chase{account.last_4_digits}_Activity{date_from:%Y%m%d}_{date_to:%Y%m%d}_{download_date:%Y%m%d}.CSV"
                yield CreditCardStatement(account, os.path.join(self.config.statements_download_dir, expected_filename))

    def pull_totals_for_date(self, date_from):
        expected_name = SheetUploader.sheet_name(date_from)
        if not self.api.sheet_exists(expected_name):
            logging.warning(f"Could not find sheet with expected name '{expected_name}'")
            s = self.api.find_sheet_by_prefix(expected_name)
            if s is None:
                logging.error(f"Could not find sheet with prefix '{expected_name}'")
                return
            else:
                expected_name = s.title
        yield from self.pull_totals(expected_name)

    def pull_totals(self, sheet_name):
        sheet = self.api.sheet.worksheet_by_title(sheet_name)
        items = sheet.get_col(SHEET_CATEGORY_COL, include_tailing_empty=False)
        values = sheet.get_col(SHEET_CATEGORY_COL + 1, include_tailing_empty=False)
        for i, v in zip(items[SHEET_CATEGORY_ROW:-1], values[SHEET_CATEGORY_ROW:-1]):
            yield ExpenseTotal(i, float(v))


if __name__ == '__main__':
    config = cfg.get_configuration()

    today = dt.datetime(2020, 3, 31)
    feb1 = dt.datetime(2020, 2, 1)
    feb29 = dt.datetime(2020, 2, 29)

    uploader = SheetUploader(config)
    #uploader.upload_statements(feb1, feb29, today)

    expenses = uploader.pull_totals_for_date(feb1)
    for e in expenses:
        print(e)


