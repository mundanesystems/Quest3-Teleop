import socket
import time

def test_udp_listener():
    """Simple UDP listener to test Quest gyroscope data"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 9050))
    sock.settimeout(1.0)
    
    print("Listening for Quest gyroscope data on port 9050...")
    print("Make sure your Quest 3 app is running and sending data.")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            try:
                data, addr = sock.recvfrom(1024)
                message = data.decode('utf-8')
                print(f"Received from {addr}: {message}")
                
                # Parse the data
                try:
                    values = message.split(',')
                    pitch = float(values[0])
                    yaw = float(values[1])
                    print(f"  -> Pitch: {pitch:.1f}°, Yaw: {yaw:.1f}°")
                except (ValueError, IndexError):
                    print(f"  -> Invalid data format: {message}")
                    
            except socket.timeout:
                print("No data received in the last second...")
                continue
                
    except KeyboardInterrupt:
        print("\nStopping UDP listener.")
    finally:
        sock.close()

if __name__ == "__main__":
    test_udp_listener()
