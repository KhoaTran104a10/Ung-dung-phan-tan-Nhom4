# sample_data.py
from tinydb import TinyDB, Query
import os

DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Định nghĩa đường dẫn file DB
db_leader_path = f'{DATA_DIR}/leader_db.json'
db_f1_path = f'{DATA_DIR}/follower1_db.json'
db_f2_path = f'{DATA_DIR}/follower2_db.json'

# Xóa dữ liệu cũ (nếu có)
for path in [db_leader_path, db_f1_path, db_f2_path]:
    if os.path.exists(path):
        os.remove(path)

# Khởi tạo DB
db_leader = TinyDB(db_leader_path)
db_f1 = TinyDB(db_f1_path)
db_f2 = TinyDB(db_f2_path)

# Chèn dữ liệu ban đầu - mỗi nút có dữ liệu riêng (partitioned)
# Dữ liệu này *không* được sao chép, để mô phỏng kịch bản scatter-gather
# trên dữ liệu phân tán (sharded/partitioned).

# Nút Leader (Node 1)
db_leader.insert_multiple([
    {'name': 'Alice', 'age': 30, 'city': 'New York'},
    {'name': 'Bob', 'age': 25, 'city': 'New York'}
])

# Nút Follower 1 (Node 2)
db_f1.insert_multiple([
    {'name': 'Charlie', 'age': 35, 'city': 'London'},
    {'name': 'David', 'age': 22, 'city': 'London'}
])

# Nút Follower 2 (Node 3)
db_f2.insert_multiple([
    {'name': 'Eve', 'age': 40, 'city': 'Tokyo'},
    {'name': 'Frank', 'age': 28, 'city': 'Tokyo'}
])

print(f"Đã tạo dữ liệu mẫu phân tán tại thư mục '{DATA_DIR}'.")
print(f" - Leader: {db_leader_path} (2 bản ghi)")
print(f" - Follower 1: {db_f1_path} (2 bản ghi)")
print(f" - Follower 2: {db_f2_path} (2 bản ghi)")