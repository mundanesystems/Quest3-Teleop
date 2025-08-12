import socket
import time

print("Starting bare-bones debug server on port 8080...")
server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_sock.bind(('0.0.0.0', 8080))
server_sock.listen(1)

print("Waiting for a client to connect...")
conn, addr = server_sock.accept()
print(f"✅ Client connected from {addr}")

counter = 0
try:
    while True:
        message = f"Message from server: {counter}\n".encode('utf-8')
        conn.sendall(message)
        print(f"Sent: Message {counter}")
        counter += 1
        time.sleep(1)
except Exception as e:
    print(f"Connection lost: {e}")
finally:
    conn.close()
    print("Connection closed.")