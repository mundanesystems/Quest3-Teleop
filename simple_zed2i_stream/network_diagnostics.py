import socket
import time
import threading
import statistics

def ping_test(host, port, count=10):
    """Simple TCP ping test"""
    times = []
    
    for i in range(count):
        try:
            start = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            end = time.time()
            sock.close()
            
            if result == 0:
                rtt = (end - start) * 1000
                times.append(rtt)
                print(f"Ping {i+1}: {rtt:.1f}ms")
            else:
                print(f"Ping {i+1}: Failed to connect")
        except Exception as e:
            print(f"Ping {i+1}: Error - {e}")
        
        time.sleep(0.1)
    
    if times:
        avg = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        jitter = statistics.stdev(times) if len(times) > 1 else 0
        
        print(f"\n--- Network Statistics ---")
        print(f"Average RTT: {avg:.1f}ms")
        print(f"Min RTT: {min_time:.1f}ms")
        print(f"Max RTT: {max_time:.1f}ms")
        print(f"Jitter: {jitter:.1f}ms")
        print(f"Success rate: {len(times)}/{count} ({len(times)/count*100:.1f}%)")
        
        if avg > 100:
            print("\n🚨 HIGH LATENCY DETECTED!")
            print("Possible causes:")
            print("- WiFi interference or weak signal")
            print("- Network congestion")
            print("- Router/switch issues")
            print("- Background network activity")
        elif avg > 50:
            print("\n⚠️ MODERATE LATENCY")
            print("Network is slower than optimal for real-time streaming")
        else:
            print("\n✅ GOOD LATENCY")
            print("Network performance looks good")

def bandwidth_test():
    """Simple bandwidth estimation"""
    print("\n--- Quick Bandwidth Test ---")
    data_size = 1024 * 1024  # 1MB test
    test_data = b'x' * data_size
    
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('localhost', 9999))
        server_socket.listen(1)
        
        def server():
            conn, addr = server_socket.accept()
            start = time.time()
            conn.sendall(test_data)
            end = time.time()
            conn.close()
            
            transfer_time = end - start
            bandwidth = (data_size / transfer_time) / (1024 * 1024)  # MB/s
            print(f"Localhost bandwidth: {bandwidth:.1f} MB/s")
        
        server_thread = threading.Thread(target=server)
        server_thread.start()
        
        time.sleep(0.1)
        
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(('localhost', 9999))
        received = b''
        while len(received) < data_size:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            received += chunk
        client_socket.close()
        
        server_thread.join()
        server_socket.close()
        
    except Exception as e:
        print(f"Bandwidth test failed: {e}")

if __name__ == "__main__":
    print("🔍 Network Diagnostics for WebRTC Streaming")
    print("=" * 50)
    
    # Test local network connectivity
    print("\n1. Testing local network (router)...")
    ping_test("192.168.0.1", 80, 5)  # Common router IP
    
    print("\n2. Testing to your WebRTC server...")
    ping_test("192.168.0.196", 8080, 10)
    
    print("\n3. Testing internet connectivity...")
    ping_test("8.8.8.8", 53, 5)  # Google DNS
    
    # Quick bandwidth test
    bandwidth_test()
    
    print("\n" + "=" * 50)
    print("💡 Tips to reduce latency:")
    print("- Use wired Ethernet instead of WiFi")
    print("- Close other network-heavy applications")
    print("- Check for router firmware updates")
    print("- Reduce video resolution/quality")
    print("- Use 5GHz WiFi instead of 2.4GHz")
