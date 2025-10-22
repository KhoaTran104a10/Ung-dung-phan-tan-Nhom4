# run_demo.py
# Kịch bản để khởi động và dừng toàn bộ hệ thống demo một cách dễ dàng.
import subprocess
import time
import sys
import requests
import os

# --- Cấu hình các Node ---
NODES_CONFIG = {
    "leader": {
        "script": "leader.py",
        "port": 5000,
        "dbfile": "leader_db.json"
    },
    "followers": [
        {
            "script": "follower.py",
            "port": 5001,
            "dbfile": "follower1_db.json"
        },
        {
            "script": "follower.py",
            "port": 5002,
            "dbfile": "follower2_db.json"
        }
    ]
}
# -------------------------

# Lưu trữ các tiến trình đang chạy
running_processes = []

def cleanup_db_files():
    """Xóa các file database cũ để bắt đầu một demo mới."""
    print("Đang dọn dẹp các file database cũ...")
    if os.path.exists(NODES_CONFIG["leader"]["dbfile"]):
        os.remove(NODES_CONFIG["leader"]["dbfile"])
    for follower in NODES_CONFIG["followers"]:
        if os.path.exists(follower["dbfile"]):
            os.remove(follower["dbfile"])
    print("Dọn dẹp hoàn tất.")

def start_nodes():
    """Bắt đầu chạy Leader và các Follower node."""
    cleanup_db_files()
    print("--- Bắt đầu khởi chạy các Node ---")
    
    # Khởi chạy Leader
    leader_config = NODES_CONFIG["leader"]
    leader_cmd = [sys.executable, leader_config["script"]]
    # Sử dụng Popen để các tiến trình chạy ngầm
    process = subprocess.Popen(leader_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    running_processes.append(process)
    print(f"Đã khởi chạy Leader trên cổng {leader_config['port']}...")
    
    # Đợi một chút để leader sẵn sàng
    time.sleep(1)

    # Khởi chạy các Followers
    for follower_config in NODES_CONFIG["followers"]:
        follower_cmd = [
            sys.executable, 
            follower_config["script"],
            f"--port={follower_config['port']}",
            f"--dbfile={follower_config['dbfile']}"
        ]
        process = subprocess.Popen(follower_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        running_processes.append(process)
        print(f"Đã khởi chạy Follower trên cổng {follower_config['port']}...")

    print("\n--- Tất cả các node đã được khởi chạy! ---")
    print("Mở file 'client.html' để bắt đầu.")
    print("Chạy 'python populate_demo.py' để tạo dữ liệu mẫu.")
    print("Nhấn Ctrl+C hoặc chạy 'python run_demo.py stop' để dừng lại.")

def stop_nodes():
    """Dừng tất cả các node đang chạy."""
    print("\n--- Bắt đầu dừng các Node ---")
    
    # Dừng Followers trước
    for follower_config in reversed(NODES_CONFIG["followers"]):
        try:
            url = f"http://127.0.0.1:{follower_config['port']}/shutdown"
            requests.post(url, timeout=1)
            print(f"Đã gửi yêu cầu dừng đến Follower trên cổng {follower_config['port']}.")
        except requests.exceptions.RequestException:
            # Bỏ qua lỗi nếu node đã dừng
            pass

    # Dừng Leader
    leader_config = NODES_CONFIG["leader"]
    try:
        url = f"http://127.0.0.1:{leader_config['port']}/shutdown"
        requests.post(url, timeout=1)
        print(f"Đã gửi yêu cầu dừng đến Leader trên cổng {leader_config['port']}.")
    except requests.exceptions.RequestException:
        # Bỏ qua lỗi nếu node đã dừng
        pass
    
    print("\n--- Hoàn tất dừng các Node ---")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "start":
            start_nodes()
            try:
                # Giữ script chạy để theo dõi các tiến trình
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                stop_nodes()
        elif command == "stop":
            stop_nodes()
        else:
            print(f"Lệnh không xác định: {command}")
            print("Sử dụng: 'python run_demo.py start' hoặc 'python run_demo.py stop'")
    else:
        print("Vui lòng cung cấp lệnh: 'start' hoặc 'stop'")
        print("Ví dụ: python run_demo.py start")

