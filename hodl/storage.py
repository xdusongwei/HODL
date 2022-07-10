import json
from datetime import timedelta
from dataclasses import dataclass
import sqlite3
from hodl.state import *
from hodl.tools import FormatTool, TimeTools


@dataclass
class EarningRow:
    day: int
    symbol: str
    amount: int
    unit: str
    region: str
    broker: str
    buyback_price: float
    create_time: int
    id: int = None

    def save(self, con: sqlite3.Connection):
        with con:
            con.execute(
                "INSERT INTO `earning`(`day`, `symbol`, `amount`, `unit`, `region`, `broker`, `buyback_price`, `create_time`) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                (
                    self.day,
                    self.symbol,
                    self.amount,
                    self.unit,
                    self.region,
                    self.broker,
                    self.buyback_price,
                    self.create_time,
                ))

    @classmethod
    def items_after_time(cls, con: sqlite3.Connection, create_time: int):
        cur = con.cursor()
        cur.execute("SELECT * FROM `earning` WHERE create_time >= ? ORDER BY `create_time` DESC;", (create_time,))
        items = cur.fetchall()
        items = map(lambda item: EarningRow(**item), items)
        return items

    @classmethod
    def total_amount_before_time(cls, con: sqlite3.Connection, create_time: int, unit: str) -> int:
        cur = con.cursor()
        cur.execute("SELECT SUM(`amount`) FROM `earning` WHERE create_time < ? AND `unit` = ?;", (create_time, unit, ))
        item = cur.fetchone()[0]
        return item or 0

    @classmethod
    def latest_earning_by_symbol(cls, con: sqlite3.Connection, symbol: str):
        cur = con.cursor()
        cur.execute("SELECT * FROM `earning` WHERE symbol = ? ORDER BY `day` DESC LIMIT 1;", (symbol, ))
        row = cur.fetchone()
        if row:
            item = EarningRow(**row)
            return item
        return None

    @classmethod
    def total_earning_group_by_month(cls, con: sqlite3.Connection, month=6):
        @dataclass
        class _MonthlyEarning:
            month: int
            region: str
            total: int

        begin_date = TimeTools.utc_now() + timedelta(days=-30 * month)
        begin_month = int(begin_date.strftime('%Y%m'))
        cur = con.cursor()
        cur.execute(
            "SELECT substr( `day`, 1, 6) AS `month`, `region`, sum(`amount`) AS `total` "
            "FROM `earning` "
            "WHERE `day` >= ? "
            "GROUP BY substr( `day`, 1, 6), `region` "
            "ORDER BY substr( `day`, 1, 6) DESC, `region`;", (begin_month,))
        items = cur.fetchall()
        items = list(map(lambda item: _MonthlyEarning(**item), items))
        return items


@dataclass
class OrderRow:
    unique_id: str
    symbol: str
    order_id: str
    region: str
    broker: str
    content: str
    create_time: int
    update_time: int
    id: int = None

    def save(self, con: sqlite3.Connection):
        with con:
            con.execute(
                "REPLACE INTO `orders`"
                "(`unique_id`, `symbol`, `order_id`, `region`, `broker`, `content`, `create_time`, `update_time`) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                (
                    self.unique_id,
                    self.symbol,
                    self.order_id,
                    self.region,
                    self.broker,
                    self.content,
                    self.create_time,
                    self.update_time,
                ))

    @classmethod
    def items_after_create_time(cls, con: sqlite3.Connection, create_time: int):
        cur = con.cursor()
        cur.execute("SELECT * FROM `orders` WHERE `create_time` >= ? ORDER BY `create_time` DESC;", (create_time,))
        items = cur.fetchall()
        items = map(lambda item: OrderRow(**item), items)
        return items

    def summary(self) -> str:
        if not self.content:
            return f'空白订单 id={self.id}'
        d: dict = json.loads(self.content)
        order = Order(d)
        time_str = FormatTool.pretty_dt(
            v=order.create_timestamp,
            region=order.region,
            with_tz=True,
            with_year=False,
        )[:-10]
        level = order.level
        order_price = FormatTool.pretty_usd(order.limit_price, region=order.region)
        total_qty = FormatTool.pretty_number(order.qty)
        filled_price = FormatTool.pretty_usd(order.avg_price, region=order.region)
        filled_qty = FormatTool.pretty_number(order.filled_qty)
        if order.is_filled:
            filled_detail = '成交'
        elif order.filled_qty:
            filled_detail = f'部成:{filled_price}@{filled_qty}'
        else:
            filled_detail = '0成交'
        return f'{time_str}: {order.symbol} {order.direction}[{level}] {order_price}@{total_qty} {filled_detail}\n'


@dataclass
class StateRow:
    day: int
    symbol: str
    content: str
    update_time: int
    id: int = None

    def save(self, con: sqlite3.Connection):
        with con:
            con.execute(
                "REPLACE INTO `state_archive`(`day`, `symbol`, `content`, `update_time`) "
                "VALUES (?, ?, ?, ?);",
                (
                    self.day,
                    self.symbol,
                    self.content,
                    self.update_time,
                ))

    @classmethod
    def query_by_symbol_latest(cls, con: sqlite3.Connection, symbol: str):
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM `state_archive` WHERE `symbol` = ? ORDER BY `day` DESC LIMIT 1;",
            (symbol, )
        )
        row = cur.fetchone()
        if row:
            item = StateRow(**row)
            return item
        return None


@dataclass
class TempBasePriceRow:
    symbol: str
    price: float
    expiry_time: int
    update_time: int
    id: int = None

    @classmethod
    def query_by_symbol(cls, con: sqlite3.Connection, symbol: str):
        ts = int(TimeTools.us_time_now().timestamp())
        cur = con.cursor()
        cur.execute(
            "SELECT * FROM `temp_base_price` WHERE symbol = ? AND expiry_time > ? LIMIT 1;",
            (symbol, ts, )
        )
        row = cur.fetchone()
        if row:
            item = TempBasePriceRow(**row)
            return item
        return None

    def save(self, con: sqlite3.Connection):
        with con:
            con.execute(
                "REPLACE INTO `temp_base_price`(`symbol`, `price`, `expiry_time`, `update_time`) "
                "VALUES (?, ?, ?, ?);",
                (
                    self.symbol,
                    self.price,
                    self.expiry_time,
                    self.update_time,
                ))


@dataclass
class AlarmRow:
    key: str
    is_set: int
    symbol: str = None
    broker: str = None
    update_time: int = None
    id: int = None

    def save(self, con: sqlite3.Connection):
        with con:
            con.execute(
                "REPLACE INTO `alarm`(`key`, `is_set`, `symbol`, `broker`, `update_time`) "
                "VALUES (?, ?, ?, ?, ?);",
                (
                    self.key,
                    self.is_set,
                    self.symbol,
                    self.broker,
                    self.update_time,
                ))

    @classmethod
    def query_by_key(cls, con: sqlite3.Connection, key: str):
        cur = con.cursor()
        cur.execute("SELECT * FROM `alarm` WHERE `key` = ?;", (key,))
        item = cur.fetchone()
        if item:
            return AlarmRow(**item)
        return AlarmRow(
            key=key,
            is_set=False,
        )


class LocalDb:
    def __init__(self, db_path):
        con = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS earning (
        id INTEGER PRIMARY KEY, 
        `day` INTEGER NOT NULL,
        `symbol` TEXT NOT NULL,
        `amount` INTEGER NOT NULL,
        `unit` TEXT NOT NULL,
        `region` TEXT NOT NULL,
        `broker` TEXT NOT NULL,
        `buyback_price` REAL,
        `create_time` INTEGER NOT NULL
        );''')
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_create_time_symbol ON `earning` (`create_time`, `symbol`);')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_earning_symbol_day ON `earning` (`symbol`, `day`);')

        cur.execute('''CREATE TABLE IF NOT EXISTS `state_archive` (
                id INTEGER PRIMARY KEY, 
                `day` INTEGER NOT NULL,
                `symbol` TEXT NOT NULL,
                `content` BLOB NOT NULL,
                `update_time` INTEGER NOT NULL
                );''')
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_state_archive_main ON `state_archive` (`symbol`, `day`);')

        cur.execute('''CREATE TABLE IF NOT EXISTS `orders` (
                        id INTEGER PRIMARY KEY, 
                        `unique_id` TEXT NOT NULL,
                        `symbol` TEXT NOT NULL,
                        `order_id` TEXT NOT NULL,
                        'region' TEXT NOT NULL,
                        'broker' TEXT NOT NULL,
                        `content` BLOB NOT NULL,
                        'create_time' INTEGER NOT NULL,
                        `update_time` INTEGER NOT NULL
                        );''')
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_unique_id ON `orders` (`unique_id`);')

        cur.execute('''CREATE TABLE IF NOT EXISTS `alarm` (
                                id INTEGER PRIMARY KEY, 
                                `key` TEXT NOT NULL,
                                `is_set` INTEGER NOT NULL,
                                `symbol` TEXT NOT NULL,
                                'broker' TEXT NOT NULL,
                                `update_time` INTEGER NOT NULL
                                );''')
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_alarm_main ON `alarm` (`key`);')

        cur.execute('''CREATE TABLE IF NOT EXISTS `temp_base_price` (
                                        id INTEGER PRIMARY KEY, 
                                        `symbol` TEXT NOT NULL,
                                        `price` REAL NOT NULL,
                                        `expiry_time` INTEGER NOT NULL,
                                        `update_time` INTEGER NOT NULL
                                        );''')
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_temp_base_price_main ON `temp_base_price` (`symbol`);')
        con.commit()
        self.conn = con


__all__ = [
    'LocalDb',
    'EarningRow',
    'StateRow',
    'OrderRow',
    'AlarmRow',
    'TempBasePriceRow',
]
