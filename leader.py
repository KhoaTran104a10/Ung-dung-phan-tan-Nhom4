# leader.py
# Đóng vai trò là Coordinator và Leader Node

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from tinydb import TinyDB, Query
import requests
import concurrent.futures

# --- Cấu hình ---
FOLLOWER_NODES = [
    "http://127.0.0.1:5001",
    "http://127.0.0.1:5002",
]
LEADER_DB_PATH = "leader_db.json"
# -----------------

app = Flask(__name__)
CORS(app)

# Khởi tạo instance TinyDB cho Leader
db = TinyDB(LEADER_DB_PATH)

def replicate_to_followers(data):
    """Gửi yêu cầu sao chép dữ liệu đến tất cả các Follower."""
    for follower in FOLLOWER_NODES:
        try:
            requests.post(f"{follower}/replicate", json=data, timeout=2)
            print(f"Leader -> Follower: Sao chép thành công đến {follower}")
        except requests.exceptions.RequestException as e:
            print(f"Leader -> Follower: Lỗi sao chép đến {follower}: {e}")

@app.route('/insert', methods=['POST'])
def handle_insert():
    """API để client chèn dữ liệu mới (Leader-Follower)."""
    data = request.get_json()
    if not data or 'document' not in data:
        return jsonify({"error": "Dữ liệu không hợp lệ"}), 400

    document = data['document']
    
    try:
        db.insert(document)
        print(f"Leader: Đã chèn vào DB cục bộ: {document}")
    except Exception as e:
        return jsonify({"error": f"Lỗi khi ghi vào DB của Leader: {e}"}), 500

    replicate_to_followers(data)
    return jsonify({"status": "success", "message": "Dữ liệu đã được chèn và yêu cầu sao chép đã được gửi đi."})

def perform_local_search(query_data):
    """Thực hiện tìm kiếm trên DB cục bộ của Leader."""
    User = Query()
    key, op, value = query_data['key'], query_data['op'], query_data['value']
    
    ops = {'>': lambda k, v: k > v, '<': lambda k, v: k < v, '==': lambda k, v: k == v}
    if op in ops:
        return db.search(ops[op](User[key], value))
    return []

@app.route('/search', methods=['POST'])
def handle_search():
    """API để client truy vấn dữ liệu (Scatter-Gather)."""
    query_info = request.get_json()
    if not query_info or 'query' not in query_info:
        return jsonify({"error": "Truy vấn không hợp lệ"}), 400

    query_data = query_info['query']
    all_results = []
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_node = {}
        all_nodes = FOLLOWER_NODES + ["leader"]
        
        for node_url in all_nodes:
            if node_url == "leader":
                future = executor.submit(perform_local_search, query_data)
            else:
                future = executor.submit(requests.post, f"{node_url}/local_search", json=query_info, timeout=3)
            future_to_node[future] = node_url

        for future in concurrent.futures.as_completed(future_to_node):
            node = future_to_node[future]
            try:
                if node == "leader":
                    result_data = future.result()
                    print(f"Coordinator: Nhận kết quả từ Leader: {len(result_data)} bản ghi")
                else:
                    response = future.result()
                    result_data = response.json().get('results', []) if response.status_code == 200 else []
                    print(f"Coordinator: Nhận kết quả từ {node}: {len(result_data)} bản ghi")
                all_results.extend(result_data)
            except Exception as exc:
                print(f'Coordinator: Node {node} tạo ra exception: {exc}')

    unique_results = [dict(t) for t in {tuple(d.items()) for d in all_results}]
    return jsonify({"results": unique_results})

@app.route('/status', methods=['GET'])
def get_status():
    """API để client kiểm tra trạng thái các node."""
    return jsonify({"leader": "http://127.0.0.1:5000", "followers": FOLLOWER_NODES})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Endpoint để dừng Flask server."""
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    return 'Server shutting down...'

if __name__ == '__main__':
    if os.path.exists(LEADER_DB_PATH):
        os.remove(LEADER_DB_PATH)
    print("Leader node đang chạy trên cổng 5000...")
    app.run(port=5000, debug=False)

