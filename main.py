import sqlite3
import threading

from flask import Flask, request, Response
import hashlib
from functools import wraps

# 创建Flask应用
from tcpModule import start_tcp_server

app = Flask(__name__)

# 连接到SQLite数据库
conn = sqlite3.connect('cfg.sqlite3')
cursor = conn.cursor()

# 创建设备表
cursor.execute('''
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
cursor.execute('''
    CREATE TABLE IF NOT EXISTS passthrough (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_a_id INTEGER,
        device_b_id INTEGER,
        FOREIGN KEY (device_a_id) REFERENCES devices (id),
        FOREIGN KEY (device_b_id) REFERENCES devices (id)
    )
''')

# 创建配置表
cursor.execute('''
    CREATE TABLE IF NOT EXISTS config (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        value TEXT
    )
''')

# 插入默认配置项
def insert_default_config(name, default_value):
    cursor.execute('SELECT value FROM config WHERE name=?', (name,))
    value = cursor.fetchone()
    if value:
        return value[0]
    else:
        cursor.execute('INSERT INTO config (name, value) VALUES (?, ?)', (name, default_value))
        conn.commit()
        return default_value

# 从config表中读取tcpPort配置项，默认为12346
tcp_port = insert_default_config('tcpPort', '12346')

# 从config表中读取udpPort配置项，默认为12347
udp_port = insert_default_config('udpPort', '12347')

# 从config表中读取webPort配置项，默认为12345
web_port = insert_default_config('webPort', '12345')

# 从config表中读取webUser配置项，默认为admin
web_user = insert_default_config('webUser', 'admin')

# 从config表中读取webPassword配置项，默认为admin
web_password = insert_default_config('webPassword', 'admin')

# 计算webPassword的哈希值
password_hash = hashlib.sha256(web_password.encode()).hexdigest()

# 提交更改并关闭数据库连接
conn.commit()
conn.close()


# 身份验证装饰器
def authenticate(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not (auth.username == web_user and hashlib.sha256(auth.password.encode()).hexdigest() == password_hash):
            return Response('身份验证失败！', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return func(*args, **kwargs)
    return wrapper


# 首页
@app.route('/')
@authenticate
def index():
    html = '<h1>透传云首页</h1>'
    html += '<a href="/devices">设备管理</a><br>'
    html += '<a href="/passthrough">透传组管理</a><br>'
    html += '<a href="/config">配置管理</a><br>'
    return html


# 设备管理页面
@app.route('/devices')
@authenticate
def devices():
    conn = sqlite3.connect('cfg.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices')
    devices = cursor.fetchall()
    conn.close()

    # 构建设备管理页面的HTML
    html = '<h1>设备管理</h1>'
    html += '<a href="/devices/create">添加设备</a><br><br>'
    html += '<h2>在线设备</h2>'
    for device in devices:
        if device[5] == 1:
            html += f'<p>设备ID: {device[0]}, 备注: {device[1]}, 协议: {device[2]}, 用户名: {device[3]}, 密码: {device[4]} '
            html += f'<a href="/devices/edit/{device[0]}">修改</a> '
            html += f'<a href="/devices/delete/{device[0]}">删除</a></p>'

    html += '<h2>离线设备</h2>'
    for device in devices:
        if device[5] == 0:
            html += f'<p>设备ID: {device[0]}, 备注: {device[1]}, 协议: {device[2]}, 用户名: {device[3]}, 密码: {device[4]} '
            html += f'<a href="/devices/edit/{device[0]}">修改</a> '
            html += f'<a href="/devices/delete/{device[0]}">删除</a></p>'

    return html


# 创建设备页面
@app.route('/devices/create', methods=['GET', 'POST'])
@authenticate
def create_device():
    if request.method == 'POST':
        note = request.form['note']
        protocol = request.form['protocol']
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('cfg.sqlite3')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO devices (note, protocol, username, password) VALUES (?, ?, ?, ?)',
                       (note, protocol, username, password))
        conn.commit()
        conn.close()

        return '设备创建成功！'

    # 构建创建设备页面的HTML表单
    html = '<h1>创建设备</h1>'
    html += '<form method="POST" action="/devices/create">'
    html += '<label for="note">备注：</label>'
    html += '<input type="text" id="note" name="note"><br>'
    html += '<label for="protocol">协议：</label>'
    html += '<input type="radio" id="protocol" name="protocol" value="tcpServer" checked> TCP Server'
    html += '<input type="radio" id="protocol" name="protocol" value="udpServer"> UDP Server<br>'
    html += '<label for="username">用户名：</label>'
    html += '<input type="text" id="username" name="username"><br>'
    html += '<label for="password">密码：</label>'
    html += '<input type="password" id="password" name="password"><br>'
    html += '<input type="submit" value="创建">'
    html += '</form>'

    return html


# 修改设备页面
@app.route('/devices/edit/<int:device_id>', methods=['GET', 'POST'])
@authenticate
def edit_device(device_id):
    if request.method == 'POST':
        note = request.form['note']
        protocol = request.form['protocol']
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('cfg.sqlite3')
        cursor = conn.cursor()
        cursor.execute('UPDATE devices SET note=?, protocol=?, username=?, password=? WHERE id=?',
                       (note, protocol, username, password, device_id))
        conn.commit()
        conn.close()

        return f'设备 {device_id} 修改成功！'

    # 获取设备信息
    conn = sqlite3.connect('cfg.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices WHERE id=?', (device_id,))
    device = cursor.fetchone()
    conn.close()

    if not device:
        return '设备不存在！'

    # 构建修改设备页面的HTML表单
    html = f'<h1>修改设备 {device_id}</h1>'
    html += '<form method="POST">'
    html += f'<input type="hidden" name="device_id" value="{device_id}">'
    html += '<label for="note">备注：</label>'
    html += f'<input type="text" id="note" name="note" value="{device[1]}"><br>'
    html += '<label for="protocol">协议：</label>'
    html += f'<input type="radio" id="protocol" name="protocol" value="tcpServer" {"checked" if device[2] == "tcpServer" else ""}> TCP Server'
    html += f'<input type="radio" id="protocol" name="protocol" value="udpServer" {"checked" if device[2] == "udpServer" else ""}> UDP Server<br>'
    html += '<label for="username">用户名：</label>'
    html += f'<input type="text" id="username" name="username" value="{device[3]}"><br>'
    html += '<label for="password">密码：</label>'
    html += f'<input type="password" id="password" name="password" value="{device[4]}"><br>'
    html += '<input type="submit" value="修改">'
    html += '</form>'

    return html


# 删除设备页面
@app.route('/devices/delete/<int:device_id>', methods=['GET', 'POST'])
@authenticate
def delete_device(device_id):
    if request.method == 'POST':
        conn = sqlite3.connect('cfg.sqlite3')
        cursor = conn.cursor()

        # 删除设备相关的透传组
        cursor.execute('DELETE FROM passthrough WHERE device_a_id=? OR device_b_id=?', (device_id, device_id))

        # 删除设备
        cursor.execute('DELETE FROM devices WHERE id=?', (device_id,))

        conn.commit()
        conn.close()

        return f'设备 {device_id} 删除成功！'

    # 获取设备信息
    conn = sqlite3.connect('cfg.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices WHERE id=?', (device_id,))
    device = cursor.fetchone()
    conn.close()

    if not device:
        return '设备不存在！'

    # 构建删除设备页面的HTML表单
    html = f'<h1>删除设备 {device_id}</h1>'
    html += '<form method="POST">'
    html += f'<input type="hidden" name="device_id" value="{device_id}">'
    html += '<p>确定要删除该设备吗？</p>'
    html += '<input type="submit" value="删除">'
    html += '</form>'

    return html


# 查看透传列表页面
@app.route('/passthrough')
@authenticate
def view_passthrough():
    conn = sqlite3.connect('cfg.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT p.id, d1.note || " (" || d1.username || "—" || d1.password || "—" || d1.protocol || "—" || CASE WHEN d1.online = 1 THEN "在线" ELSE "离线" END || ")" AS device_a_info, '
                   'd2.note || " (" || d2.username || "—" || d2.password || "—" || d2.protocol || "—" || CASE WHEN d2.online = 1 THEN "在线" ELSE "离线" END || ")" AS device_b_info '
                   'FROM passthrough p '
                   'JOIN devices d1 ON p.device_a_id = d1.id '
                   'JOIN devices d2 ON p.device_b_id = d2.id')
    passthrough_list = cursor.fetchall()
    conn.close()

    # 构建查看透传列表页面的HTML
    html = '<h1>透传列表</h1>'
    html += '<a href="/passthrough/create">创建透传列表</a><br><br>'
    html += '<table>'
    html += '<tr><th>ID</th><th>设备A</th><th>设备B</th><th>操作</th></tr>'
    for passthrough_item in passthrough_list:
        html += f'<tr><td>{passthrough_item[0]}</td><td>{passthrough_item[1]}</td><td>{passthrough_item[2]}</td>'
        html += f'<td><a href="/passthrough/edit/{passthrough_item[0]}">修改</a> '
        html += f'<a href="/passthrough/delete/{passthrough_item[0]}">删除</a></td></tr>'
    html += '</table>'

    return html


# 创建透传列表页面
@app.route('/passthrough/create', methods=['GET', 'POST'])
def create_passthrough():
    if request.method == 'POST':
        device_a_id = request.form['device_a_id']
        device_b_id = request.form['device_b_id']

        conn = sqlite3.connect('cfg.sqlite3')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO passthrough (device_a_id, device_b_id) VALUES (?, ?)', (device_a_id, device_b_id))
        conn.commit()
        conn.close()

        return '透传列表创建成功！'

    conn = sqlite3.connect('cfg.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM devices')
    devices = cursor.fetchall()
    conn.close()

    # 构建创建透传列表页面的HTML
    html = '''
        <h1>创建透传列表</h1>
        <form method="post" action="/passthrough/create">
            <label for="device_a_id">设备A:</label>
            <select id="device_a_id" name="device_a_id">
    '''

    for device in devices:
        html += f'<option value="{device[0]}">{device[1]} ({device[3]}——{device[4]}——{device[2]}——{"在线" if device[5] == 1 else "离线"})</option>'

    html += '''
            </select><br>
            <label for="device_b_id">设备B:</label>
            <select id="device_b_id" name="device_b_id">
    '''

    for device in devices:
        html += f'<option value="{device[0]}">{device[1]} ({device[3]}——{device[4]}——{device[2]}——{"在线" if device[5] == 1 else "离线"})</option>'

    html += '''
            </select><br>
            <input type="submit" value="创建">
        </form>
    '''

    return html


# 修改透传列表页面
@app.route('/passthrough/edit/<int:passthrough_id>', methods=['GET', 'POST'])
def edit_passthrough(passthrough_id):
    if request.method == 'POST':
        device_a_id = request.form['device_a_id']
        device_b_id = request.form['device_b_id']

        conn = sqlite3.connect('cfg.sqlite3')
        cursor = conn.cursor()
        cursor.execute('UPDATE passthrough SET device_a_id=?, device_b_id=? WHERE id=?',
                       (device_a_id, device_b_id, passthrough_id))
        conn.commit()
        conn.close()

        return '透传列表修改成功！'

    conn = sqlite3.connect('cfg.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM passthrough WHERE id=?', (passthrough_id,))
    passthrough = cursor.fetchone()
    cursor.execute('SELECT * FROM devices')
    devices = cursor.fetchall()
    conn.close()

    # 构建修改透传列表页面的HTML
    html = f'''
        <h1>修改透传列表</h1>
        <form method="post" action="/passthrough/edit/{passthrough_id}">
            <label for="device_a_id">设备A:</label>
            <select id="device_a_id" name="device_a_id">
    '''

    for device in devices:
        selected = 'selected' if device[0] == passthrough[1] else ''
        html += f'<option value="{device[0]}" {selected}>{device[1]} ({device[3]}——{device[4]}——{device[2]}——{"在线" if device[5] == 1 else "离线"})</option>'

    html += '''
            </select><br>
            <label for="device_b_id">设备B:</label>
            <select id="device_b_id" name="device_b_id">
    '''

    for device in devices:
        selected = 'selected' if device[0] == passthrough[2] else ''
        html += f'<option value="{device[0]}" {selected}>{device[1]} ({device[3]}——{device[4]}——{device[2]}——{"在线" if device[5] == 1 else "离线"})</option>'

    html += '''
            </select><br>
            <input type="submit" value="保存">
        </form>
    '''

    return html


# 删除透传列表页面
@app.route('/passthrough/delete/<int:passthrough_id>')
def delete_passthrough(passthrough_id):
    conn = sqlite3.connect('cfg.sqlite3')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM passthrough WHERE id=?', (passthrough_id,))
    conn.commit()
    conn.close()

    return '透传列表删除成功！'


# 配置管理页面
@app.route('/config')
@authenticate
def config():
    conn = sqlite3.connect('cfg.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM config')
    config_items = cursor.fetchall()
    conn.close()

    # 构建配置管理页面的HTML
    html = '<h1>配置管理</h1>'
    html += '<a href="/config/create">添加配置项</a><br><br>'
    html += '<table>'
    html += '<tr><th>名称</th><th>值</th><th>操作</th></tr>'
    for config_item in config_items:
        html += f'<tr><td>{config_item[1]}</td><td>{config_item[2]}</td>'
        html += f'<td><a href="/config/edit/{config_item[0]}">修改</a> '
        html += f'<a href="/config/delete/{config_item[0]}">删除</a></td></tr>'
    html += '</table>'

    return html


# 创建配置项页面
@app.route('/config/create', methods=['GET', 'POST'])
@authenticate
def create_config():
    if request.method == 'POST':
        name = request.form['name']
        value = request.form['value']

        conn = sqlite3.connect('cfg.sqlite3')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO config (name, value) VALUES (?, ?)', (name, value))
        conn.commit()
        conn.close()

        return '配置项创建成功！'

    # 构建创建配置项页面的HTML表单
    html = '<h1>创建配置项</h1>'
    html += '<form method="POST" action="/config/create">'
    html += '<label for="name">名称：</label>'
    html += '<input type="text" id="name" name="name"><br>'
    html += '<label for="value">值：</label>'
    html += '<input type="text" id="value" name="value"><br>'
    html += '<input type="submit" value="创建">'
    html += '</form>'

    return html


# 修改配置项页面
@app.route('/config/edit/<int:config_id>', methods=['GET', 'POST'])
@authenticate
def edit_config(config_id):
    if request.method == 'POST':
        name = request.form['name']
        value = request.form['value']

        conn = sqlite3.connect('cfg.sqlite3')
        cursor = conn.cursor()
        cursor.execute('UPDATE config SET name=?, value=? WHERE id=?', (name, value, config_id))
        conn.commit()
        conn.close()

        return f'配置项 {config_id} 修改成功！'

    # 获取配置项信息
    conn = sqlite3.connect('cfg.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM config WHERE id=?', (config_id,))
    config_item = cursor.fetchone()
    conn.close()

    if not config_item:
        return '配置项不存在！'

    # 构建修改配置项页面的HTML表单
    html = f'<h1>修改配置项 {config_id}</h1>'
    html += '<form method="POST">'
    html += f'<input type="hidden" name="config_id" value="{config_id}">'
    html += '<label for="name">名称：</label>'
    html += f'<input type="text" id="name" name="name" value="{config_item[1]}"><br>'
    html += '<label for="value">值：</label>'
    html += f'<input type="text" id="value" name="value" value="{config_item[2]}"><br>'
    html += '<input type="submit" value="修改">'
    html += '</form>'

    return html


# 删除配置项页面
@app.route('/config/delete/<int:config_id>', methods=['GET', 'POST'])
@authenticate
def delete_config(config_id):
    if request.method == 'POST':
        conn = sqlite3.connect('cfg.sqlite3')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM config WHERE id=?', (config_id,))
        conn.commit()
        conn.close()

        return f'配置项 {config_id} 删除成功！'

    # 获取配置项信息
    conn = sqlite3.connect('cfg.sqlite3')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM config WHERE id=?', (config_id,))
    config_item = cursor.fetchone()
    conn.close()

    if not config_item:
        return '配置项不存在！'

    # 构建删除配置项页面的HTML表单
    html = f'<h1>删除配置项 {config_id}</h1>'
    html += '<form method="POST">'
    html += f'<input type="hidden" name="config_id" value="{config_id}">'
    html += '<p>确定要删除该配置项吗？</p>'
    html += '<input type="submit" value="删除">'
    html += '</form>'

    return html


# 运行Flask应用
if __name__ == '__main__':
    # 在其他地方调用函数启动TCP服务器
    thread = threading.Thread(target=start_tcp_server)
    thread.daemon = True
    thread.start()
    app.run(host='0.0.0.0', port=web_port)


