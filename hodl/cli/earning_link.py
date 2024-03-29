from hodl.tools import *
from hodl.storage import *

var = VariableTools()
assert var.db_path
db = LocalDb(var.db_path)


symbol = input('symbol:\n')
broker = input('broker(可以是tiger, citics):\n')
region = input('region(可以是US, CN, HK):\n')
day = int(input('day(格式为yyyymmdd, 例如20220102):\n'))
currency = input('currency(可以是USD, CNY, HKD):\n')
amount = int(input('获利金额amount:\n'))
unit = FormatTool.currency_to_unit(currency=currency)
create_time = int(TimeTools.us_time_now().timestamp())

print(f'\n\nsymbol:{symbol}\nbroker:{broker}\nregion:{region}\nday:{day}\ncurrency:{currency}\namount:{amount}\nunit:{unit}\ncreate_time:{create_time}\n')
input('确认?')

earning = EarningRow(
    day=day,
    symbol=symbol,
    currency=currency,
    days=None,
    amount=amount,
    unit=unit,
    region=region,
    broker=broker,
    buyback_price=None,
    max_level=0,
    state_version=None,
    create_time=create_time,
)
earning.save(con=db.conn)

print('已完成')
