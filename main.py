from flask import Flask, request, Response
import hashlib
from functools import wraps
from tcp.tcp_server import TCPServer
from flask import render_template
from databases.DB import DB

app = Flask(__name__, template_folder='templates')
# 设置数据库位置
db_file = "./databases/cfg.sqlite3"
# 数据处理对象
db = DB(db_file)
# 初始化配置表，存在会自动掠过
db.initConfigTable()
# 从config表中读取tcpPort配置项，默认为12346
tcp_port = db.insert_default_config('tcpPort', '12346')
# 从config表中读取udpPort配置项，默认为12347
udp_port = db.insert_default_config('udpPort', '12347')
# 从config表中读取webPort配置项，默认为12345
web_port = db.insert_default_config('webPort', '12345')
# 从config表中读取webUser配置项，默认为admin
web_user = db.insert_default_config('webUser', 'admin')
# 从config表中读取webPassword配置项，默认为admin
web_password = db.insert_default_config('webPassword', 'admin')
# 计算webPassword的哈希值
password_hash = hashlib.sha256(web_password.encode()).hexdigest()


# 身份验证装饰器
def authenticate(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not (
                auth.username == web_user and hashlib.sha256(auth.password.encode()).hexdigest() == password_hash):
            return Response('身份验证失败！', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return func(*args, **kwargs)
    return wrapper


# 首页
@app.route('/')
@authenticate
def index():
    return render_template('index.html')


# 设备管理页面
@app.route('/devices')
@authenticate
def devices():
    devices = db.select('devices')
    return render_template('devices.html', devices=devices)


# 创建设备页面
@app.route('/devices/create', methods=['GET', 'POST'])
@authenticate
def create_device():
    if request.method == 'POST':
        note = request.form['note']
        protocol = request.form['protocol']
        username = request.form['username']
        password = request.form['password']
        data = {'note': note, 'protocol': protocol, 'username': username, 'password': password}
        db.insert('devices', data)
        return '设备创建成功！'
    return render_template('create_device.html')


# 修改设备页面
@app.route('/devices/edit/<int:device_id>', methods=['GET', 'POST'])
@authenticate
def edit_device(device_id):
    if request.method == 'POST':
        note = request.form['note']
        protocol = request.form['protocol']
        username = request.form['username']
        password = request.form['password']
        data = {'note': note, 'protocol': protocol, 'username': username, 'password': password}
        condition = f"id={device_id}"
        db.update('devices', data, condition)
        return f'设备 {device_id} 修改成功！'
    # 获取设备信息
    condition = f"id={device_id}"
    device = db.select('devices', '*', condition)[0]
    if not device:
        return '设备不存在！'
    return render_template('edit_device.html', device=device)


# 删除设备页面
@app.route('/devices/delete/<int:device_id>', methods=['GET', 'POST'])
@authenticate
def delete_device(device_id):
    if request.method == 'POST':
        # 删除设备相关的透传组
        condition = f"device_a_id={device_id} OR device_b_id={device_id}"
        db.delete('passthrough', condition)
        # 删除设备
        condition = f"id={device_id}"
        db.delete('devices', condition)
        return f'设备 {device_id} 删除成功！'
    # 获取设备信息
    condition = f"id={device_id}"
    device = db.select('devices', '*', condition)[0]
    if not device:
        return '设备不存在！'
    return render_template('delete_device.html', device=device)


# 查看透传列表页面
@app.route('/passthrough')
@authenticate
def view_passthrough():
    sql = 'SELECT p.id, d1.note || " (" || d1.username || "—" || d1.password || "—" || d1.protocol || "—" || CASE WHEN d1.online = 1 THEN "在线" ELSE "离线" END || ")" AS device_a_info, ' \
          'd2.note || " (" || d2.username || "—" || d2.password || "—" || d2.protocol || "—" || CASE WHEN d2.online = 1 THEN "在线" ELSE "离线" END || ")" AS device_b_info ' \
          'FROM passthrough p ' \
          'JOIN devices d1 ON p.device_a_id = d1.id ' \
          'JOIN devices d2 ON p.device_b_id = d2.id'
    passthrough_list = db.executeSql(sql)
    return render_template('passthrough.html', passthrough_list=passthrough_list)


# 创建透传列表页面
@app.route('/passthrough/create', methods=['GET', 'POST'])
def create_passthrough():
    if request.method == 'POST':
        device_a_id = request.form['device_a_id']
        device_b_id = request.form['device_b_id']
        data = {'device_a_id': device_a_id, 'device_b_id': device_b_id}
        db.insert('passthrough', data)
        return '透传列表创建成功！'
    devices = db.select('devices')
    return render_template('create_passthrough.html', devices=devices)


# 修改透传列表页面
@app.route('/passthrough/edit/<int:passthrough_id>', methods=['GET', 'POST'])
def edit_passthrough(passthrough_id):
    if request.method == 'POST':
        device_a_id = request.form['device_a_id']
        device_b_id = request.form['device_b_id']
        data = {'device_a_id': device_a_id, 'device_b_id': device_b_id}
        condition = f"id={passthrough_id}"
        db.update('passthrough', data, condition)
        return '透传列表修改成功！'
    condition = f"id={passthrough_id}"
    passthrough = db.select('passthrough', '*', condition)[0]
    devices = db.select('devices')
    return render_template('edit_passthrough.html', passthrough_id=passthrough_id, passthrough=passthrough, devices=devices)


# 删除透传列表页面
@app.route('/passthrough/delete/<int:passthrough_id>')
def delete_passthrough(passthrough_id):
    condition = f"id={passthrough_id}"
    db.delete('passthrough', condition)
    return '透传列表删除成功！'


# 配置管理页面
@app.route('/config')
@authenticate
def config():
    config_items = db.select('config')
    return render_template('config.html', config_items=config_items)


# 创建配置项页面
@app.route('/config/create', methods=['GET', 'POST'])
@authenticate
def create_config():
    if request.method == 'POST':
        name = request.form['name']
        value = request.form['value']
        data = {'name': name, 'value': value}
        db.insert('config', data)
        return '配置项创建成功！'
    return render_template('create_config.html')


# 修改配置项页面
@app.route('/config/edit/<int:config_id>', methods=['GET', 'POST'])
@authenticate
def edit_config(config_id):
    if request.method == 'POST':
        name = request.form['name']
        value = request.form['value']
        # data = {'value': '12346'}
        # condition = "name='webPort'"
        data = {'name': name, 'value': value}
        condition = f"id='{config_id}'"
        db.update('config', data, condition)
        return f'配置项 {config_id} 修改成功！'
    # 获取配置项信息
    condition = f"id={config_id}"
    config_item = db.select('config', '*', condition)[0]
    if not config_item:
        return '配置项不存在！'
    return render_template('edit_config.html', config_id=config_id, config_item=config_item)


# 删除配置项页面
@app.route('/config/delete/<int:config_id>', methods=['GET', 'POST'])
@authenticate
def delete_config(config_id):
    if request.method == 'POST':
        condition = f"id={config_id}"
        db.delete('config', condition)
        return f'配置项 {config_id} 删除成功！'
    # 获取配置项信息
    condition = f"id={config_id}"
    config_item = db.select('config', '*', condition)[0]
    if not config_item:
        return '配置项不存在！'
    return render_template('delete_config.html', config_id=config_id)


# 运行Flask应用
if __name__ == '__main__':
    tcp_server = TCPServer(db_file).start()
    # app.debug = True
    app.run(host='0.0.0.0', port=web_port)
