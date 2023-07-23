import sqlite3
import threading
import socket
import hashlib

def start_tcp_server():
    # 连接到SQLite数据库
    conn = sqlite3.connect('cfg.sqlite3', check_same_thread=False)
    cursor = conn.cursor()

    # 获取数据库中的端口号
    cursor.execute('SELECT value FROM config WHERE name="tcpPort"')
    tcp_port = int(cursor.fetchone()[0])

    # 将协议类型为tcpServer的设备的在线状态改为0
    cursor.execute('UPDATE devices SET online=0 WHERE protocol="tcpServer"')
    conn.commit()

    # 创建字典用于存储设备连接
    device_connections = {}

    # 创建锁对象用于线程同步
    lock = threading.Lock()

    # 函数用于处理客户端连接
    def handle_client_connection(client_socket):
        # 发送"whoAreYou"消息给客户端
        send_response(client_socket, 'whoAreYou')
        while True:
            try:
                data = client_socket.recv(1024).decode()
                if not data:
                    break
                # 解析用户名和密码
                username, password = parse_credentials(data)
                # 验证用户名和密码是否匹配
                if verify_credentials(username, password):
                    # 登录成功
                    device_id = get_device_id(username)
                    if device_id is None:
                        # send_response(client_socket, 'loginFail')
                        break

                    # 检查设备在线状态
                    if is_device_online(device_id):
                        # send_response(client_socket, 'loginFail')
                        break

                    # 更新设备在线状态为1
                    update_device_online_status(device_id, 1)

                    # 关联设备ID和连接
                    add_device_connection(device_id, client_socket)

                    # 打印提示信息
                    print(f"设备 {device_id} 登录成功！")

                    # 接收并处理后续消息
                    while True:
                        data = client_socket.recv(1024).decode()
                        if not data:
                            break

                        # 打印接收到的消息
                        print(f"收到设备 {device_id} 的消息: {data}")

                        # 转发消息给其他设备
                        forward_message(device_id, data)
                else:
                    # 登录失败
                    send_response(client_socket, 'loginFail')
                    break
            except Exception as e:
                print(f"发生错误：{str(e)}")
                break

        # 获取设备ID
        device_id = get_device_id_by_socket(client_socket)
        if device_id:
            # 更新设备在线状态为0
            update_device_online_status(device_id, 0)
            # 移除设备连接
            remove_device_connection(device_id)

        # 关闭客户端连接
        client_socket.close()

    # 函数用于解析用户名和密码
    def parse_credentials(data):
        username_start = data.find("username:") + len("username:")
        username_end = data.find(".password:")
        username = data[username_start:username_end]

        password_start = data.find("password:") + len("password:")
        password = data[password_start:]

        return username, password

    # 函数用于验证用户名和密码是否匹配
    def verify_credentials(username, password):
        # 获取数据库中的账号密码
        cursor.execute('SELECT username, password FROM devices WHERE protocol="tcpServer"')
        credentials = cursor.fetchall()
        for credential in credentials:
            # if credential[0] == username and hashlib.sha256(password.encode()).hexdigest() == credential[1]:
            if credential[0] == username and password == credential[1]:
                return True
        return False

    # 函数用于发送响应消息给客户端
    def send_response(client_socket, message):
        client_socket.send(message.encode())

    # 函数用于获取设备ID
    def get_device_id(username):
        cursor.execute('SELECT id FROM devices WHERE username=?', (username,))
        result = cursor.fetchone()
        if result:
            return result[0]
        return None

    # 函数用于检查设备在线状态
    def is_device_online(device_id):
        cursor.execute('SELECT online FROM devices WHERE id=?', (device_id,))
        result = cursor.fetchone()
        if result and result[0] == 1:
            return True
        return False

    # 函数用于更新设备的在线状态
    def update_device_online_status(device_id, online_status):
        cursor.execute('UPDATE devices SET online=? WHERE id=?', (online_status, device_id))
        conn.commit()

    # 函数用于添加设备连接到字典中
    def add_device_connection(device_id, client_socket):
        with lock:
            device_connections[device_id] = client_socket

    # 函数用于移除设备连接
    def remove_device_connection(device_id):
        with lock:
            if device_id in device_connections:
                del device_connections[device_id]

    # 函数用于转发消息给其他设备
    def forward_message(device_id, message):
        cursor.execute('SELECT device_b_id FROM passthrough WHERE device_a_id=?', (device_id,))
        target_device_ids = cursor.fetchall()
        for target_device_id in target_device_ids:
            target_device_id = target_device_id[0]
            if target_device_id in device_connections:
                target_socket = device_connections[target_device_id]
                target_socket.send(message.encode())
            else:
                print(f"设备 {target_device_id} 不在线！")

    # 函数用于根据客户端连接获取设备ID
    def get_device_id_by_socket(client_socket):
        with lock:
            for device_id, socket in device_connections.items():
                if socket == client_socket:
                    return device_id
        return None

    # 创建TCP服务器
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', tcp_port))
    server_socket.listen(5)

    print(f"TCP服务器正在监听端口 {tcp_port}...")

    # 接收并处理客户端连接
    while True:
        client_socket, address = server_socket.accept()
        client_thread = threading.Thread(target=handle_client_connection, args=(client_socket,))
        client_thread.start()

# 在其他地方调用函数启动TCP服务器
# start_tcp_server()
