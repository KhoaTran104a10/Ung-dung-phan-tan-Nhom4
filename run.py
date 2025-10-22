# run.py
import subprocess
import time
import sys
import os

# --- Cấu hình các nút ---
PORT_LEADER = 5000
PORT_F1 = 5001
PORT_F2 = 5002

DB_PATH_LEADER = 'data/leader_db.json'
DB_PATH_F1 = 'data/follower1_db.json'
DB_PATH_F2 = 'data/follower2_db.json'

URL_LEADER = f"http://127.0.0.1:{PORT_LEADER}"
URL_F1 = f"http://127.0.0.1:{PORT_F1}"
URL_F2 = f"http://127.0.0.1:{PORT_F2}"
# -------------------------

# Kiểm tra xem có đang chạy trong virtual environment không
if sys.prefix == sys.base_prefix:
    print("CẢNH BÁO: Bạn nên chạy file này trong một môi trường ảo (virtual environment).")
    print("Hãy tạo bằng lệnh: python -m venv venv")
    print("Và kích hoạt nó (ví dụ trên Windows): .\\venv\\Scripts\\activate")
    time.sleep(3)

# 1. Chạy script tạo dữ liệu mẫu
print("="*50)
print("Bước 1: Khởi tạo dữ liệu mẫu...")
print("="*50)
# Sử dụng sys.executable để đảm bảo dùng đúng trình thông dịch python
subprocess.run([sys.executable, 'sample_data.py'], check=True)
print("\n")


# 2. Khởi chạy các nút
print("="*50)
print("Bước 2: Khởi chạy các nút...")
print("="*50)

processes = []
try:
    # 2.1. Khởi chạy Leader Node
    leader_cmd = [
        sys.executable, 'nodes/leader.py',
        '--port', str(PORT_LEADER),
        '--db', DB_PATH_LEADER,
        '--followers', f'{URL_F1},{URL_F2}'
    ]
    # Popen không block, và chúng ta chuyển hướng output vào DEVNULL để terminal chính gọn gàng
    # Bạn có thể bỏ stdout và stderr để xem log của từng tiến trình ngay tại đây
    print(f"Đang khởi chạy Leader trên cổng {PORT_LEADER}...")
    leader_process = subprocess.Popen(leader_cmd, stdout=sys.stdout, stderr=sys.stderr)
    processes.append(leader_process)
    
    # 2.2. Khởi chạy Follower 1
    f1_cmd = [
        sys.executable, 'nodes/follower.py',
        '--port', str(PORT_F1),
        '--db', DB_PATH_F1
    ]
    print(f"Đang khởi chạy Follower 1 trên cổng {PORT_F1}...")
    f1_process = subprocess.Popen(f1_cmd, stdout=sys.stdout, stderr=sys.stderr)
    processes.append(f1_process)

    # 2.3. Khởi chạy Follower 2
    f2_cmd = [
        sys.executable, 'nodes/follower.py',
        '--port', str(PORT_F2),
        '--db', DB_PATH_F2
    ]
    print(f"Đang khởi chạy Follower 2 trên cổng {PORT_F2}...")
    f2_process = subprocess.Popen(f2_cmd, stdout=sys.stdout, stderr=sys.stderr)
    processes.append(f2_process)
    
    print("\n" + "="*50)
    print("TẤT CẢ CÁC NÚT ĐÃ SẴN SÀNG!")
    print(f"==> Mở trình duyệt và truy cập: {URL_LEADER}")
    print("="*50)
    print("\nNhấn (Ctrl+C) trong terminal này để tắt tất cả các nút.")
    
    # Giữ cho script chính chạy
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n\nĐang tắt tất cả các nút...")
    for p in processes:
        p.terminate() # Gửi tín hiệu dừng
    
    # Đợi các tiến trình con kết thúc
    for p in processes:
        p.wait()
        
    print("Đã tắt hệ thống. Tạm biệt!")
except Exception as e:
    print(f"Đã xảy ra lỗi: {e}")
    print("Đang cố gắng dọn dẹp...")
    for p in processes:
        p.terminate()
        p.wait()