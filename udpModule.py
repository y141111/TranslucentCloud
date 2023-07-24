import sqlite3
import threading
import socket


def start_udp_server():
    # 连接到SQLite数据库
    conn = sqlite3.connect('cfg.sqlite3', check_same_thread=False)
    cursor = conn.cursor()

    # 获取数据库中的端口号
    cursor.execute('SELECT value FROM config WHERE name="udpPort"')
    udp_port = int(cursor.fetchone()[0])

    # 创建字典用于存储设备连接
    device_connections = {}

    # 创建锁对象用于线程同步
    lock = threading.Lock()

    # 函数用于处理客户端连接
    def handle_client_connection(client_socket, address):
        device_id = None
        while True:
            try:
                data = client_socket.recv(1024).decode()
                if not data:
                    break
                device_id = get_device_id_by_address(address)
                if address not in device_connections.values():  # 未登录状态
                    # 解析接收到的消息
                    if data.startswith("username:") and data.count(".") == 1:
                        username, password = data.split(".")
                        username = username.split(":")[1]
                        password = password.split(":")[1]

                        # 根据用户名和密码验证登录
                        if verify_credentials(username, password):
                            device_id = username  # 使用username作为设备ID
                            add_device_connection(device_id, address)
                            send_response(client_socket, 'loginSuccess')
                            print(f" {address} ")
                            print(f"设备 {device_id} 登录成功！")
                        else:
                            send_response(client_socket, 'loginFailed')
                            print(f"设备登录失败！")
                    else:
                        send_response(client_socket, 'loginRequired')
                else:  # 登录状态
                    # 打印接收到的消息
                    print(f" {address} ")
                    print(f"收到设备 {device_id} 的消息: {data}")

                    # 转发消息给其他设备
                    forward_message(device_id, data)

            except Exception as e:
                print(f"发生错误：{str(e)}")
                break

        # 关闭客户端连接
        client_socket.close()
        # 移除设备连接
        remove_device_connection(device_id)

    # 函数用于发送响应消息给客户端
    def send_response(client_socket, message):
        client_socket.sendto(message.encode(), client_address)

    # 函数用于获取设备ID
    def get_device_id_by_address(address):
        with lock:
            for device_id, client_address in device_connections.items():
                if client_address == address:
                    return device_id
        return None

    # 函数用于验证用户名和密码是否匹配
    def verify_credentials(username, password):
        # 获取数据库中的账号密码
        cursor.execute('SELECT username, password FROM devices WHERE protocol="udpServer"')
        credentials = cursor.fetchall()
        for credential in credentials:
            # if credential[0] == username and hashlib.sha256(password.encode()).hexdigest() == credential[1]:
            if credential[0] == username and password == credential[1]:
                return True
        return False

    # 函数用于添加设备连接到字典中
    def add_device_connection(device_id, client_address):
        with lock:
            device_connections[device_id] = client_address

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
                target_address = device_connections[target_device_id]
                server_socket.sendto(message.encode(), target_address)
            else:
                print(f"设备 {target_device_id} 不在线！")

    # 创建UDP服务器
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('0.0.0.0', udp_port))

    print(f"UDP服务器正在监听端口 {udp_port}...")

    # 接收并处理客户端连接
    while True:
        data, client_address = server_socket.recvfrom(1024)
        client_thread = threading.Thread(target=handle_client_connection, args=(server_socket, client_address))
        client_thread.start()

# 在其他地方调用函数启动UDP服务器
# start_udp_server()
