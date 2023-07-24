import socket
import time

def udp_server(host, port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((host, port))
    print("UDP服务器已启动，等待客户端连接...")

    while True:
        data, address = server_socket.recvfrom(1024)  # 接收客户端消息
        message = "hi! {}:{}".format(address[0], address[1]).encode("utf-8")
        server_socket.sendto(message, address)  # 向客户端发送消息
        print("已向客户端发送消息：{}".format(message.decode("utf-8")))
        time.sleep(1)  # 每秒发送一次消息

    server_socket.close()

if __name__ == "__main__":
    udp_server("0.0.0.0", 9999)
