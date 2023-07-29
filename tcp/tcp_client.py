import datetime
import socket
import threading
import time


class TCPClient:

    def __init__(self, server_ip, server_port):
        self.client_socket = None
        self.server_ip = server_ip
        self.server_port = server_port
        self.connect()
        self.receive_thread = threading.Thread(target=self.receive_message)
        self.receive_thread.daemon = True
        self.receive_thread.start()

    def connect(self):
        try:
            print(f"开始连接 {self.server_ip}:{self.server_port}")
            self.disconnect()
            self.client_socket = None
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_ip, self.server_port))
            print(f"连接成功！！！！")
        except Exception as e:
            # 100570: Connection reset by peer
            if str(e).find("100570") != -1:
                print(f"远程服务器100570错误")
            # 10061: Connection refused
            elif str(e).find("10061") != -1:
                print(f"远程服务器10061错误，连接被拒绝，TCPServer未开启或没有网络")
            else:
                print(f"线程名称{threading.current_thread().name}连接失败:{e}")

    def disconnect(self):
        if self.client_socket:
            self.client_socket.close()

    def receive_message(self):
        while True:
            try:
                data = self.client_socket.recv(1024)
                if not data:
                    print(f"收到空数据,正在重连...")
                    self.connect()
                    continue
                print("收到消息:", data)
            except Exception as e:
                # 10054: An existing connection was forcibly closed by the remote host
                if str(e).find("10054") != -1:
                    print(f"收到10054错误，远程主机强迫关闭了一个现有的连接")
                elif str(e).find("10057") != -1:
                    pass
                else:
                    print(f"接收消息异常:{e}")
                self.connect()
                continue

    def send_data(self, data):
        try:
            self.client_socket.send(data)
            return True
        except Exception as e:
            # 10057: An established connection was aborted by the software in your host machine
            if str(e).find("10057") != -1:
                print(f"未连接上，发送失败")
                return False
            # 10054: An existing connection was forcibly closed by the remote host
            else:
                print(f"发送异常:{e}")
                return False

    def send_data_utf8(self, data):
        try:
            self.client_socket.send(data.encode("utf8"))
            return True
        except Exception as e:
            # 10057: An established connection was aborted by the software in your host machine
            if str(e).find("10057") != -1:
                print(f"未连接上，发送失败")
                return False
            # 10054: An existing connection was forcibly closed by the remote host
            else:
                print(f"发送异常:{e}")
                return False


if __name__ == "__main__":
    def read_input(client):
        input_text = input()
        print("发送:", input_text)
        client.send_data(input_text.encode())
    client1 = TCPClient("192.168.0.22", 8000)
    while True:
        read_input(client1)
