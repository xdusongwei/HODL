import sqlite3
import threading
from datetime import timedelta
from dataclasses import dataclass, field
from hodl.state import *
from hodl.tools import FormatTool, TimeTools


@dataclass
class EarningRow:
    day: int
    symbol: str
    currency: str
    days: int
    amount: int
    unit: str
    region: str
    broker: str
    buyback_price: float
    max_level: int
    state_version: str
    create_time: int
    id: int = None

    def save(self, con: sqlite3.Connection):
        with con:
            con.execute(
                "INSERT INTO `earning`"
                "(`day`, `symbol`, `currency`, `days`, `amount`, `unit`, `region`, `broker`, `buyback_price`, `max_level`, `state_version`, `create_time`) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
                (
                    self.day,
                    self.symbol,
                    self.currency,
                    self.days,
                    self.amount,
                    self.unit,
                    self.region,
                    self.broker,
                    self.buyback_price,
                    self.max_level,
                    self.state_version,
                    self.create_time,
                ))

    @classmethod
    def items_after_time(cls, con: sqlite3.Connection, create_time: int):
        sql = "SELECT * FROM `earning` WHERE create_time >= ? ORDER BY `create_time` DESC;"
        with con:
            cur = con.cursor()
            cur.execute(sql, (create_time,))
            items = cur.fetchall()
        items = map(lambda item: EarningRow(**item), items)
        return items

    @classmethod
    def total_amount_before_time(cls, con: sqlite3.Connection, create_time: int, currency: str) -> int:
        with con:
            cur = con.cursor()
            cur.execute("SELECT SUM(`amount`) FROM `earning` WHERE create_time < ? AND `currency` = ?;",
                        (create_time, currency,))
            item = cur.fetchone()[0]
        return item or 0

    @classmethod
    def latest_earning_by_symbol(cls, con: sqlite3.Connection, symbol: str, days: int = 14):
        sql = "SELECT * FROM `earning` WHERE `symbol` = ? AND `buyback_price` IS NOT NULL AND `day` >= ? " \
              "ORDER BY `day` DESC LIMIT 1;"
        begin_date = TimeTools.timedelta(TimeTools.utc_now(), days=-days)
        begin_day = int(begin_date.strftime('%Y%m%d'))
        with con:
            cur = con.cursor()
            cur.execute(sql, (symbol, begin_day,))
            row = cur.fetchone()
        if row:
            item = EarningRow(**row)
            return item
        return None

    @classmethod
    def latest_earning_by_symbol_broker(cls, con: sqlite3.Connection, broker: str, symbol: str, days: int = 14):
        sql = "SELECT * FROM `earning` " \
              "WHERE `symbol` = ? AND `buyback_price` IS NOT NULL AND `broker` = ? AND `day` >= ? " \
              "ORDER BY `day` DESC LIMIT 1;"
        begin_date = TimeTools.timedelta(TimeTools.utc_now(), days=-days)
        begin_day = int(begin_date.strftime('%Y%m%d'))
        with con:
            cur = con.cursor()
            cur.execute(sql, (symbol, broker, begin_day,))
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
            currency: str
            total: int

        begin_date = TimeTools.utc_now() + timedelta(days=-30 * month)
        begin_month = int(begin_date.strftime('%Y%m'))
        with con:
            cur = con.cursor()
            cur.execute(
                "SELECT substr( `day`, 1, 6) AS `month`, `currency`, sum(`amount`) AS `total` "
                "FROM `earning` "
                "WHERE `day` >= ? "
                "GROUP BY substr( `day`, 1, 6), `currency` "
                "ORDER BY substr( `day`, 1, 6) DESC, `currency`;", (begin_month,))
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
    create_time: int
    update_time: int
    content: str = field(default=None)
    id: int = field(default=None)

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
        sql = "SELECT * FROM `orders` WHERE `create_time` >= ? ORDER BY `create_time` DESC;"
        with con:
            cur = con.cursor()
            cur.execute(sql, (create_time,))
            items = cur.fetchall()
        items = map(lambda item: OrderRow(**item), items)
        return list(items)

    @classmethod
    def simple_items_after_create_time(cls, con: sqlite3.Connection, create_time: int):
        sql = "SELECT `unique_id`, `symbol`, `order_id`, `region`, `broker`, `create_time`, `update_time` " \
              "FROM `orders` WHERE `create_time` >= ? ORDER BY `create_time` DESC;"
        with con:
            cur = con.cursor()
            cur.execute(sql, (create_time,))
            items = cur.fetchall()
        items = map(lambda item: OrderRow(**item), items)
        return items

    def summary(self) -> str:
        if not self.content:
            return f'空白订单 id={self.id}'
        d: dict = FormatTool.json_loads(self.content)
        order = Order(d)
        time_str = FormatTool.pretty_dt(
            v=order.create_timestamp,
            region=order.region,
            with_tz=True,
            with_year=False,
        )[:-10]
        level = order.level
        order_price = FormatTool.pretty_usd(order.limit_price, currency=order.currency)
        total_qty = FormatTool.pretty_number(order.qty)
        filled_price = FormatTool.pretty_usd(order.avg_price, currency=order.currency)
        filled_qty = FormatTool.pretty_number(order.filled_qty)
        if order.is_filled:
            filled_detail = f'成交:{filled_price}@{filled_qty}'
        elif order.filled_qty:
            filled_detail = f'部成:{filled_price}@{filled_qty}'
        else:
            filled_detail = '--'
        full_symbol = f'[{order.broker}]{order.region}.{order.symbol}'
        emoji = order.order_emoji
        return f'{emoji}{full_symbol} {order.direction}#{level}\n{time_str}\n{order_price}@{total_qty}\n{filled_detail}\n'


@dataclass
class StateRow:
    version: str
    day: int
    symbol: str
    content: str
    update_time: int
    id: int = None

    def save(self, con: sqlite3.Connection):
        with con:
            con.execute(
                "REPLACE INTO `state_archive`(`version`, `day`, `symbol`, `content`, `update_time`) "
                "VALUES (?, ?, ?, ?, ?);",
                (
                    self.version,
                    self.day,
                    self.symbol,
                    self.content,
                    self.update_time,
                ))

    @classmethod
    def query_by_symbol_latest(cls, con: sqlite3.Connection, symbol: str):
        with con:
            cur = con.cursor()
            cur.execute(
                "SELECT * FROM `state_archive` WHERE `symbol` = ? ORDER BY `version` DESC LIMIT 1;",
                (symbol,)
            )
            row = cur.fetchone()
        if row:
            item = StateRow(**row)
            return item
        return None


@dataclass
class TempBasePriceRow:
    broker: str
    symbol: str
    price: float
    expiry_time: int
    update_time: int
    id: int = None

    @classmethod
    def query_by_symbol(cls, con: sqlite3.Connection, broker: str, symbol: str):
        ts = int(TimeTools.us_time_now().timestamp())
        with con:
            cur = con.cursor()
            cur.execute(
                "SELECT * FROM `temp_base_price` WHERE broker = ? AND symbol = ? AND expiry_time > ? ORDER BY `expiry_time` DESC LIMIT 1;",
                (broker, symbol, ts,)
            )
            row = cur.fetchone()
        if row:
            item = TempBasePriceRow(**row)
            return item
        return None

    def save(self, con: sqlite3.Connection):
        with con:
            con.execute(
                "REPLACE INTO `temp_base_price`(`broker`, `symbol`, `price`, `expiry_time`, `update_time`) "
                "VALUES (?, ?, ?, ?, ?);",
                (
                    self.broker,
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
        with con:
            cur = con.cursor()
            cur.execute("SELECT * FROM `alarm` WHERE `key` = ?;", (key,))
            item = cur.fetchone()
        if item:
            return AlarmRow(**item)
        return AlarmRow(
            key=key,
            is_set=False,
        )


@dataclass
class QuoteLowHistoryRow:
    broker: str
    region: str
    symbol: str
    day: int
    low_price: float
    update_time: int
    id: int = None

    def save(self, con: sqlite3.Connection):
        sql = "REPLACE INTO `quote_low_history`(`broker`, `region`, `symbol`, `day`, `low_price`, `update_time`) " \
              "VALUES (?, ?, ?, ?, ?, ?);"
        params = (
            self.broker,
            self.region,
            self.symbol,
            self.day,
            self.low_price,
            self.update_time,
        )
        with con:
            con.execute(sql, params)

    @classmethod
    def query_by_symbol(
            cls,
            con: sqlite3.Connection,
            broker: str,
            region: str,
            symbol: str,
            begin_day: int,
            end_day: int,
    ) -> list['QuoteLowHistoryRow']:
        sql = "SELECT `broker`, `region`, `symbol`, `day`, `low_price`, `update_time` FROM `quote_low_history` " \
              "WHERE `broker` = ? AND `region` = ? AND `symbol` = ? AND `day` >= ? AND `day` <= ? ORDER BY `day` DESC;"
        params = (broker, region, symbol, begin_day, end_day,)
        with con:
            cur = con.cursor()
            cur.execute(sql, params)
            items = cur.fetchall()
        items = list(map(lambda item: QuoteLowHistoryRow(**item), items))
        return items


@dataclass
class QuoteHighHistoryRow:
    broker: str
    region: str
    symbol: str
    day: int
    high_price: float
    update_time: int
    id: int = None

    def save(self, con: sqlite3.Connection):
        sql = "REPLACE INTO `quote_high_history`(`broker`, `region`, `symbol`, `day`, `high_price`, `update_time`) " \
              "VALUES (?, ?, ?, ?, ?, ?);"
        params = (
            self.broker,
            self.region,
            self.symbol,
            self.day,
            self.high_price,
            self.update_time,
        )
        with con:
            con.execute(sql, params)

    @classmethod
    def query_by_symbol(
            cls,
            con: sqlite3.Connection,
            broker: str,
            region: str,
            symbol: str,
            begin_day: int,
            end_day: int,
    ) -> list['QuoteHighHistoryRow']:
        sql = "SELECT `broker`, `region`, `symbol`, `day`, `high_price`, `update_time` FROM `quote_high_history` " \
              "WHERE `broker` = ? AND `region` = ? AND `symbol` = ? AND `day` >= ? AND `day` <= ? ORDER BY `day` DESC;"
        params = (broker, region, symbol, begin_day, end_day,)
        with con:
            cur = con.cursor()
            cur.execute(sql, params)
            items = cur.fetchall()
        items = list(map(lambda item: QuoteHighHistoryRow(**item), items))
        return items


class SqliteConnWithLock(sqlite3.Connection):
    DB_LOCK = threading.RLock()

    def __enter__(self):
        super().__enter__()
        SqliteConnWithLock.DB_LOCK.acquire(blocking=True)

    def __exit__(self, exc_type, exc_val, exc_tb):
        SqliteConnWithLock.DB_LOCK.release()
        super().__exit__(exc_type, exc_val, exc_tb)


class LocalDb:
    def __init__(self, db_path):
        con = sqlite3.connect(db_path, factory=SqliteConnWithLock, check_same_thread=False, isolation_level=None)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS earning (
        id INTEGER PRIMARY KEY, 
        `day` INTEGER NOT NULL,
        `symbol` TEXT NOT NULL,
        `currency` TEXT NOT NULL,
        `days` INTEGER,
        `amount` INTEGER NOT NULL,
        `unit` TEXT NOT NULL,
        `region` TEXT NOT NULL,
        `broker` TEXT NOT NULL,
        `buyback_price` REAL,
        `max_level` INTEGER,
        `state_version` TEXT,
        `create_time` INTEGER NOT NULL
        );''')
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_create_time_symbol ON `earning` (`create_time`, `broker`, `symbol`);')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_earning_symbol_day ON `earning` (`symbol`, `day`);')

        cur.execute('''CREATE TABLE IF NOT EXISTS `state_archive` (
                id INTEGER PRIMARY KEY, 
                `version` TEXT NOT NULL,
                `day` INTEGER NOT NULL,
                `symbol` TEXT NOT NULL,
                `content` BLOB NOT NULL,
                `update_time` INTEGER NOT NULL
                );''')
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_state_archive_main ON `state_archive` (`version`);')
        cur.execute(
            'CREATE INDEX IF NOT EXISTS idx_state_archive_symbol_version ON `state_archive` (`symbol`, `version`);')

        cur.execute('''CREATE TABLE IF NOT EXISTS `orders` (
                        id INTEGER PRIMARY KEY, 
                        `unique_id` TEXT NOT NULL,
                        `symbol` TEXT NOT NULL,
                        `order_id` TEXT NOT NULL,
                        `region` TEXT NOT NULL,
                        `broker` TEXT NOT NULL,
                        `content` BLOB NOT NULL,
                        `create_time` INTEGER NOT NULL,
                        `update_time` INTEGER NOT NULL
                        );''')
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_unique_id ON `orders` (`unique_id`);')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_orders_create_time ON `orders` (`create_time`);')

        cur.execute('''CREATE TABLE IF NOT EXISTS `alarm` (
                                id INTEGER PRIMARY KEY, 
                                `key` TEXT NOT NULL,
                                `is_set` INTEGER NOT NULL,
                                `symbol` TEXT NOT NULL,
                                `broker` TEXT NOT NULL,
                                `update_time` INTEGER NOT NULL
                                );''')
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_alarm_main ON `alarm` (`key`);')

        cur.execute('''CREATE TABLE IF NOT EXISTS `temp_base_price` (
                                        id INTEGER PRIMARY KEY, 
                                        `broker` TEXT NOT NULL,
                                        `symbol` TEXT NOT NULL,
                                        `price` REAL NOT NULL,
                                        `expiry_time` INTEGER NOT NULL,
                                        `update_time` INTEGER NOT NULL
                                        );''')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_temp_base_price_main ON `temp_base_price` (`broker`, `symbol`, `expiry_time`);')

        cur.execute('''CREATE TABLE IF NOT EXISTS `quote_low_history` (
                                                id INTEGER PRIMARY KEY,
                                                `broker` TEXT NOT NULL,
                                                `region` TEXT NOT NULL,
                                                `symbol` TEXT NOT NULL,
                                                `day` INTEGER NOT NULL,
                                                `low_price` REAL NOT NULL,
                                                `update_time` INTEGER NOT NULL
                                                );''')
        cur.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_quote_low_history_search ON `quote_low_history` (`broker`, `region`, `symbol`, `day`);')

        cur.execute('''CREATE TABLE IF NOT EXISTS `quote_high_history` (
                                                        id INTEGER PRIMARY KEY,
                                                        `broker` TEXT NOT NULL,
                                                        `region` TEXT NOT NULL,
                                                        `symbol` TEXT NOT NULL,
                                                        `day` INTEGER NOT NULL,
                                                        `high_price` REAL NOT NULL,
                                                        `update_time` INTEGER NOT NULL
                                                        );''')
        cur.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_quote_high_history_search ON `quote_high_history` (`broker`, `region`, `symbol`, `day`);')

        con.commit()
        self.conn = con


__all__ = [
    'LocalDb',
    'EarningRow',
    'StateRow',
    'OrderRow',
    'AlarmRow',
    'TempBasePriceRow',
    'QuoteLowHistoryRow',
    'QuoteHighHistoryRow',
]
