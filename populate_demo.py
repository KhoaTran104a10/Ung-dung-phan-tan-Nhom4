# populate_demo.py
# Kịch bản để tự động chèn dữ liệu mẫu vào hệ thống cho mục đích demo.
import requests
import json

LEADER_URL = 'http://127.0.0.1:5000'

# Dữ liệu mẫu
SAMPLE_DATA = [
    {"name": "An", "age": 22, "city": "Hanoi"},
    {"name": "Binh", "age": 35, "city": "Da Nang"},
    {"name": "Cuong", "age": 19, "city": "Ho Chi Minh"},
    {"name": "Dung", "age": 41, "city": "Hanoi"},
    {"name": "Giang", "age": 28, "city": "Can Tho"},
    {"name": "Hoa", "age": 30, "city": "Da Nang"},
]

def populate():
    """Gửi dữ liệu mẫu đến Leader node."""
    print("--- Bắt đầu chèn dữ liệu mẫu ---")
    
    headers = {'Content-Type': 'application/json'}
    success_count = 0
    
    for record in SAMPLE_DATA:
        payload = {"document": record}
        try:
            response = requests.post(f"{LEADER_URL}/insert", data=json.dumps(payload), headers=headers)
            if response.status_code == 200:
                print(f"  + Chèn thành công: {record}")
                success_count += 1
            else:
                print(f"  - Lỗi khi chèn {record}: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"\nLỗi: Không thể kết nối đến Leader node tại {LEADER_URL}.")
            print("Hãy chắc chắn rằng bạn đã chạy 'python run_demo.py start' trước.")
            return

    print(f"\n--- Hoàn tất: Đã chèn thành công {success_count}/{len(SAMPLE_DATA)} bản ghi. ---")

if __name__ == "__main__":
    populate()

