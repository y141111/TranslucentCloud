import queue
import socket
import sqlite3
import threading
import time
from multiprocessing.pool import ThreadPool


class TCPServer(object):

    def __init__(self):
        # 列队存储要执行的数据库操作
        self.db_queue = queue.Queue()
        self.local_conn = threading.local()

        #
        threading.Thread(target=self.run_db_task).start()

        # 在初始化时连接SQLite数据库
        # self.conn = sqlite3.connect('cfg.sqlite3', check_same_thread=False)
        # self.cursor = self.conn.cursor()
        self.local_conn.conn = sqlite3.connect('cfg.sqlite3', check_same_thread=False)
        self.local_conn.cursor = self.local_conn.conn.cursor()

        # 创建连接池,最大连接数4096
        self.pool = ThreadPool(processes=4096)

        # 在初始化时启动TCP服务器
        self.start()

    def run_db_task(self):
        """
        这个函数 从队列中获取数据库操作并执行
        :return:
        """
        while True:
            func, args = self.db_queue.get()
            func(*args)
            self.db_queue.task_done()

    def start(self):
        # 获取数据库中的TCP端口号
        self.local_conn.cursor.execute('SELECT value FROM config WHERE name="tcpPort"')
        tcp_port = int(self.local_conn.cursor.fetchone()[0])

        # 将所有协议类型为tcpServer的设备设置为离线状态
        self.local_conn.cursor.execute('UPDATE devices SET online=0 WHERE protocol="tcpServer"')
        self.local_conn.conn.commit()

        # 创建字典用于存储设备连接
        self.device_connections = {}

        # 创建锁对象用于线程同步
        self.lock = threading.Lock()

        # 启动TCP服务器
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(('0.0.0.0', tcp_port))
        self.server_socket.listen(5)

        print(f"TCP服务器正在监听端口 {tcp_port}...")

        # 在独立线程中接收并处理客户端连接
        threading.Thread(target=self.handle_client_connections).start()

    def handle_client_connections(self):
        self.local_conn.conn = sqlite3.connect('cfg.sqlite3', check_same_thread=False)
        self.local_conn.cursor = self.local_conn.conn.cursor()
        while True:
            client_socket, address = self.server_socket.accept()
            # 使用连接池启动线程处理每个连接
            self.pool.apply_async(self.handle_client_connection, (client_socket,))

    def handle_client_connection(self, client_socket):

        self.local_conn.conn = sqlite3.connect('cfg.sqlite3', check_same_thread=False)
        self.local_conn.cursor = self.local_conn.conn.cursor()

        remote_addr = client_socket.getpeername()
        print(f"设备 {remote_addr} 建立连接,等待身份验证")

        # 定义发送心跳包的函数
        def send_heartbeat(device_id, username, password):
            self.local_conn.conn = sqlite3.connect('cfg.sqlite3', check_same_thread=False)
            self.local_conn.cursor = self.local_conn.conn.cursor()
            print(f"设备 {remote_addr} {device_id} {username} {password} 开启心跳包线程!")
            while True:
                time.sleep(0.5)
                try:
                    # 获取目标设备ID
                    target_device_ids = self.get_target_device_id(device_id)
                    if target_device_ids is None:
                        print("设备没有目标设备 send_heartbeat")
                        continue
                    # 判断目标设备 有没有在线的
                    for target_device_id in target_device_ids:
                        target_device_id = target_device_id[0]
                        # 如果目标设备在线,则发送心跳包
                        if target_device_id in self.device_connections:
                            client_socket.send('!'.encode('gbk'))
                            # 发送一次就行
                            continue
                        # 否则不发送
                        else:
                            continue
                except Exception as e:
                    print(f" {e} ")
                    print(f"设备 {remote_addr} 发送心跳包错误,与其断开连接")
                    break

        device_id = None
        while True:
            try:
                # 接收数据
                data = client_socket.recv(1024).decode()
                if not data:
                    print(f"设备 {remote_addr} 收到空数据")
                    print(f"设备 {remote_addr} 与其断开连接")
                    break

                # 解析用户名和密码
                username, password = self.parse_credentials(data)

                # 验证用户名和密码
                if self.verify_credentials(username, password):
                    # 登录成功

                    # 获取设备ID
                    device_id = self.get_device_id(username)
                    if device_id is None:
                        print(f"设备 {remote_addr} {username} {password} id号不存在!")
                        print(f"设备 {remote_addr} 与其断开连接")
                        device_id = None
                        break

                    # 检查设备是否已在线
                    if self.is_device_online(device_id):
                        print(f"设备 {remote_addr} {username} {password} 已在线,重复登陆!")
                        print(f"设备 {remote_addr} 与其断开连接")
                        device_id = None
                        break

                    # 更新在线状态为在线
                    self.update_device_online_status(device_id, 1)

                    # 关联设备ID和连接
                    self.add_device_connection(device_id, client_socket)

                    # 打印登录成功信息
                    print(f"设备 {remote_addr} {device_id} {username} {password} 登录成功!")

                    # 启动线程发送心跳包
                    threading.Thread(target=send_heartbeat, args=(device_id, username, password,)).start()

                    # 循环接收并转发消息
                    while True:
                        data = client_socket.recv(1024).decode()
                        if not data:
                            break
                        # 打印收到的设备信息。
                        # print(f"设备 {remote_addr} {device_id} {username} {password}  的消息: {data}")

                        # 获取目标设备ID
                        target_device_ids = self.get_target_device_id(device_id)

                        # 启动线程发送心跳包
                        # send_heartbeat(device_id, username, password, target_device_ids)

                        self.forward_message(device_id, username, password, data, remote_addr, target_device_ids)
                        # self.forward_message(device_id, username, password, data, remote_addr)

                else:
                    # 登录失败
                    print(f"设备 {remote_addr} {username} {password} 账号或密码不对!")
                    print(f"设备 {remote_addr} 与其断开连接")
                    break

            except Exception as e:
                print(f"设备 {remote_addr} 发生错误:{e}")
                print(f"设备 {remote_addr} 与其断开连接")
                break

        # 更新数据库中的在线状态
        if device_id is None:
            # 关闭客户端连接
            client_socket.close()
        else:
            print(f"{device_id} 断开这个设备！")
            self.update_device_online_status(device_id, 0)
            # 移除设备连接
            self.remove_device_connection(device_id)
            # 关闭客户端连接
            client_socket.close()
        # 关闭客户端连接
        client_socket.close()

    # 解析用户名和密码
    def parse_credentials(self, data):
        username_start = data.find("username:") + len("username:")
        username_end = data.find(".password:")
        username = data[username_start:username_end]

        password_start = data.find("password:") + len("password:")
        password = data[password_start:]

        return username, password

    # 验证用户名和密码  
    def verify_credentials(self, username, password):
        # 从数据库中获取账号密码
        self.local_conn.cursor.execute('SELECT username, password FROM devices WHERE protocol="tcpServer"')
        credentials = self.local_conn.cursor.fetchall()
        for credential in credentials:
            if credential[0] == username and credential[1] == password:
                return True
        return False

    # 获取设备ID        
    def get_device_id(self, username):
        self.local_conn.cursor.execute('SELECT id FROM devices WHERE username=?', (username,))
        result = self.local_conn.cursor.fetchone()
        if result:
            return result[0]
        return None

    # 获取目标设备ID
    def get_target_device_id(self, device_id):
        # 不直接执行数据库操作,把操作封装成一个函数,加入队列
        # def query_db():
        self.local_conn.cursor.execute('SELECT device_b_id FROM passthrough WHERE device_a_id=?', (device_id,))
        # 加入队列
        # self.db_queue.put((query_db, ()))
        # 等待队列空
        # self.db_queue.join()
        target_device_ids = self.local_conn.cursor.fetchall()
        if target_device_ids:
            return target_device_ids
        return None

    # 检查设备是否在线
    def is_device_online(self, device_id):
        self.local_conn.cursor.execute('SELECT online FROM devices WHERE id=?', (device_id,))
        result = self.local_conn.cursor.fetchone()
        if result and result[0] == 1:
            return True
        return False

    # 检查设备是否在线
    def is_device_in_device_connections(self, device_id):
        self.local_conn.cursor.execute('SELECT online FROM devices WHERE id=?', (device_id,))
        result = self.local_conn.cursor.fetchone()
        if result and result[0] == 1:
            return True
        return False

    # 更新设备在线状态
    def update_device_online_status(self, device_id, status):
        self.local_conn.cursor.execute('UPDATE devices SET online=? WHERE id=?', (status, device_id))
        self.local_conn.conn.commit()

    # 添加设备连接        
    def add_device_connection(self, device_id, socket):
        with self.lock:
            self.device_connections[device_id] = socket

    # 移除设备连接
    def remove_device_connection(self, device_id):
        with self.lock:
            if device_id in self.device_connections:
                del self.device_connections[device_id]

    # 转发消息给其他设备
    def forward_message(self, device_id, username, password, message, remote_addr, target_device_ids):
        # 获取目标设备ID
        # target_device_ids = self.get_target_device_id(device_id)
        if target_device_ids is None:
            print("设备没有目标设备 forward_message")
            return
        for target_device_id in target_device_ids:
            target_device_id = target_device_id[0]
            # 如果目标设备在线,则直接转发
            if target_device_id in self.device_connections:
                target_socket = self.device_connections[target_device_id]
                target_socket.send(message.encode())

            # 否则打印不在线提示
            else:
                print(
                    f"设备 {remote_addr} {device_id} {username} {password}  消息转发失败,设备 {target_device_id}  不在线!")

# 在其他地方调用函数启动TCP服务器
# tcp_server = TCPServer()
