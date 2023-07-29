import hashlib
import sqlite3


class DB:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()

    def initConfigTable(self):
        # 创建设备表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note TEXT,  -- 新增备注字段
                protocol TEXT,
                username TEXT,
                password TEXT,
                online INTEGER DEFAULT 0
            )
        ''')

        # 创建透传列表表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS passthrough (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_a_id INTEGER,
                device_b_id INTEGER,
                FOREIGN KEY (device_a_id) REFERENCES devices (id),
                FOREIGN KEY (device_b_id) REFERENCES devices (id)
            )
        ''')

        # 创建配置表
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                value TEXT
            )
        ''')

    # 插入默认配置项
    def insert_default_config(self, name, default_value):
        self.cursor.execute('SELECT value FROM config WHERE name=?', (name,))
        value = self.cursor.fetchone()
        if value:
            return value[0]
        else:
            self.cursor.execute('INSERT INTO config (name, value) VALUES (?, ?)', (name, default_value))
            self.conn.commit()
            return default_value

    def insert(self, table, data):
        cols = ','.join(data.keys())
        vals = ','.join(['?'] * len(data))
        sql = f'INSERT INTO {table} ({cols}) VALUES ({vals})'
        self.cursor.execute(sql, tuple(data.values()))
        self.conn.commit()

    def delete(self, table, condition):
        sql = f'DELETE FROM {table} WHERE {condition}'
        self.cursor.execute(sql)
        self.conn.commit()

    def update(self, table, data, condition):
        sql = f'UPDATE {table} SET {",".join([f"{k}=?" for k in data])} WHERE {condition}'
        values = tuple(data.values())
        self.cursor.execute(sql, values)
        self.conn.commit()

    def select(self, table, fields='*', condition=None):
        if condition is None:
            sql = f'SELECT {fields} FROM {table}'
        else:
            sql = f'SELECT {fields} FROM {table} WHERE {condition}'
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def executeSql(self, sql):
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def close(self):
        self.cursor.close()
        self.conn.close()


def test():
    db = DB('../cfg.sqlite3')
    # 插入config
    data = {'name': 'webPort', 'value': '12345'}
    db.insert('config', data)

    # 查询config
    config = db.select('config')

    # 更新config
    data = {'value': '12346'}
    condition = "name='webPort'"
    db.update('config', data, condition)

    # 删除config
    condition = "id=1"
    db.delete('config', condition)

    # 插入devices
    data = {'protocol': 'tcp', 'username': 'test', 'password': '123'}
    db.insert('devices', data)

    # 查询devices
    devices = db.select('devices')

    # 更新devices
    data = {'password': '456'}
    condition = "id=1"
    db.update('devices', data, condition)

    # 删除devices
    condition = "id=1"
    db.delete('devices', condition)

    # 插入passthrough
    data = {'device_a_id': 1, 'device_b_id': 2}
    db.insert('passthrough', data)

    # 查询passthrough
    passthrough = db.select('passthrough')

    # 更新passthrough
    data = {'device_b_id': 3}
    condition = "id=1"
    db.update('passthrough', data, condition)

    # 删除passthrough
    condition = "id=1"
    db.delete('passthrough', condition)
