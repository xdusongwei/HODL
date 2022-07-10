from hodl.storage import *
from hodl.tools import *
from hodl.store import Store


var = VariableTools()


db = LocalDb(var.db_path)
Store.rewrite_earning_csv(
    db=db,
    earning_csv_path=var.earning_csv_path,
    now=TimeTools.us_time_now(),
)

print('done')
