from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser
import configuration as cfg
import datetime as dt

__debug = False


def get_access_token(config):
    sw = Splitwise(config.splitwise_key, config.splitwise_secret)
    url, secret = sw.getAuthorizeURL()
    print(url, secret)
    oauth_token = url.split('=')[1]
    oauth_verifier = input("oauth_verfier: ")

    access_token = sw.getAccessToken(oauth_token, secret, oauth_verifier)
    print("Add access_token to configuration for next time:")
    access_token_config = str(access_token).replace("'", '"')
    print(f'"splitwise_access_token": {access_token_config}')
    return access_token


def init(config: cfg.Configuration):
    access_token = config.splitwise_access_token
    if not access_token:
        access_token = get_access_token(config)
    return Splitwise(config.splitwise_key, config.splitwise_secret, access_token)


def share_expense_with_group_members(sw: Splitwise, desc, cost, group_id, date):
    grp = sw.getGroup(group_id)
    current_user = sw.getCurrentUser()
    other_members = [m for m in grp.getMembers() if m.id != current_user.id]
    _debug(current_user)
    _debug(other_members)
    cost_per_user = round(cost / len(grp.members), 2)

    expense = Expense()
    expense.cost = f"{cost}"
    expense.description = f"{desc}"
    expense.group_id = f"{group_id}"
    expense.setDate(date.strftime("%Y/%m/%d"))

    users = []
    for om in other_members:
        user = ExpenseUser()
        user.setId(om.id)
        user.setPaidShare(f"0")
        user.setOwedShare(f"{cost_per_user}")
        users.append(user)
    user = ExpenseUser()
    user.setId(current_user.id)
    user.setPaidShare(f"{cost}")
    user.setOwedShare(f"{cost - len(users) * cost_per_user}")
    users.append(user)
    expense.users = users
    sw.createExpense(expense)


def _debug(element):
    if not __debug:
        return
    try:
        for e in element:
            print(f">>   {e.__dict__}")
    except:
        print(f"~~   {element.__dict__}")


def main():
    config = cfg.get_configuration()
    sw = init(config)
    _debug(sw.getGroups())
    _debug(sw.getFriends())

    grp_id = 19058988  # test group
    _debug(sw.getExpenses(group_id=grp_id))

    today = dt.date.today()
    share_expense_with_group_members(sw, "test_date", 10, grp_id, today)
    # share_expense_with_group_members(sw, "test_10.02", 10.02, grp_id, today)


if __name__ == '__main__':
    __debug = True
    main()
