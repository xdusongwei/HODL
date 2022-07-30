from hodl.storage import *
from hodl.tools import *
from hodl.store import Store


var = VariableTools()


db = LocalDb(var.db_path)
Store.rewrite_earning_json(
    db=db,
    earning_json_path=var.earning_json_path,
    now=TimeTools.us_time_now(),
)

print('done')
