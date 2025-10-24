# nodes/leader.py
import argparse
import requests
import uuid # 1. Thêm UUID
from flask import Flask, request, jsonify, render_template
from tinydb import TinyDB, Query, where
from concurrent.futures import ThreadPoolExecutor
import os

db = None
FOLLOWER_URLS = []
executor = ThreadPoolExecutor(max_workers=10)

# --- Logic tìm kiếm (dùng chung) ---
def perform_search(db_instance, data):
    try:
        search_name = data.get('name', '').strip()
        search_age = data.get('age', '').strip()
        search_city = data.get('city', '').strip()
        User = Query()
        conditions = []
        if search_name:
            conditions.append(where('name').test(lambda s: search_name.lower() in s.lower()))
        if search_age:
            try:
                conditions.append(User.age == int(search_age))
            except ValueError: pass
        if search_city:
            conditions.append(where('city').test(lambda s: search_city.lower() in s.lower()))
        if not conditions: return []
        final_condition = conditions.pop(0)
        for cond in conditions:
            final_condition = (final_condition & cond)
        return db_instance.search(final_condition)
    except Exception as e:
        print(f"Lỗi khi thực hiện tìm kiếm: {e}")
        return []

# ------------------------------------

def create_app(db_path, followers_list, leader_port):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    
    global db, FOLLOWER_URLS
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = TinyDB(db_path)
    FOLLOWER_URLS = followers_list
    
    app.config['LEADER_PORT'] = leader_port
    app.config['LEADER_NAME'] = f"Leader ({leader_port})"
    
    # Tạo bản đồ (map) các Node
    app.config['NODE_MAP'] = {}
    app.config['NODE_MAP'][f"http://127.0.0.1:{leader_port}"] = app.config['LEADER_NAME']
    for i, url in enumerate(FOLLOWER_URLS):
        port = url.split(':')[-1]
        app.config['NODE_MAP'][url] = f"Follower {i+1} ({port})"

    # --- 2. Hàm kiểm tra sức khỏe (Health Check) ---
    def get_system_status():
        """
        Kiểm tra trạng thái của tất cả các nút (Leader + Followers)
        """
        nodes_list = []
        health_status = {} # Dùng để lưu trạng thái cho logic sao chép

        # 1. Leader (luôn Online)
        leader_url = f"http://127.0.0.1:{app.config['LEADER_PORT']}"
        nodes_list.append({"url": leader_url, "role": app.config['LEADER_NAME'], "status": "Online"})
        health_status[app.config['LEADER_NAME']] = "Online"

        # 2. Kiểm tra các Followers
        for url in FOLLOWER_URLS:
            node_name = app.config['NODE_MAP'][url]
            try:
                response = requests.get(f"{url}/health", timeout=0.5) # Timeout 0.5s
                if response.status_code == 200:
                    nodes_list.append({"url": url, "role": node_name, "status": "Online"})
                    health_status[url] = "Online"
                else:
                    nodes_list.append({"url": url, "role": node_name, "status": "Offline"})
                    health_status[url] = "Offline"
            except requests.ConnectionError:
                nodes_list.append({"url": url, "role": node_name, "status": "Offline"})
                health_status[url] = "Offline"
        
        return nodes_list, health_status

    # --- 3. Hàm sao chép (Broadcast) nâng cao ---
    def broadcast_request(endpoint, payload, log_messages, health_status):
        """
        Gửi yêu cầu (insert, update, delete) đến các Follower đang Online.
        """
        online_followers = [url for url in FOLLOWER_URLS if health_status.get(url) == "Online"]
        
        def post_request(url):
            try:
                requests.post(f"{url}/{endpoint}", json=payload, timeout=2)
                return f"Gửi sao chép ({endpoint}) tới {app.config['NODE_MAP'][url]} thành công."
            except Exception as e:
                return f"Lỗi khi gửi sao chép ({endpoint}) tới {app.config['NODE_MAP'][url]}: {e}"

        log_messages.append(f"Bắt đầu sao chép tới {len(online_followers)} Follower(s) đang Online...")
        
        # Gửi song song
        futures = [executor.submit(post_request, url) for url in online_followers]
        
        # Thu thập log từ kết quả
        for future in futures:
            log_messages.append(future.result())

    # --- API cho Giao diện Web (Client) ---
    @app.route('/')
    def index():
        """ Hiển thị trang web chính. """
        nodes_list, _ = get_system_status()
        return render_template('index.html', 
                               results=None, 
                               message=None, 
                               nodes=nodes_list,
                               log_messages=None) # 4. Thêm log_messages=None

    @app.route('/insert', methods=['POST'])
    def insert():
        """ Xử lý yêu cầu INSERT (Tính năng 1 + 4) """
        nodes_list, health_status = get_system_status()
        log_messages = [] # 4. Khởi tạo list log
        message = ""
        message_type = "success"
        
        try:
            name = request.form['name']
            age = int(request.form['age'])
            city = request.form['city']
            doc = {'name': name, 'age': age, 'city': city}
            doc['_id'] = str(uuid.uuid4()) # 1. Gán _id duy nhất
            
            # 1. Ghi vào Leader
            db.insert(doc)
            log_messages.append(f"LEADER: Đã chèn '{name}' (ID: {doc['_id'][:8]}...) vào DB cục bộ.")
            
            # 2. Phát tán (broadcast) lệnh sao chép
            payload = {"document": doc}
            broadcast_request('replicate_insert', payload, log_messages, health_status)
            
            message = f"Thành công: Đã chèn '{name}'."
        except Exception as e:
            message = f"Lỗi: {str(e)}"
            message_type = "error"
            log_messages.append(f"Lỗi nghiêm trọng khi chèn: {e}")
        
        return render_template('index.html', 
                               results=None, 
                               message=message, 
                               message_type=message_type, 
                               nodes=nodes_list,
                               log_messages=log_messages) # 4. Truyền log ra
    
    # --- 1. API MỚI: UPDATE ---
    @app.route('/update', methods=['POST'])
    def update():
        """ Xử lý yêu cầu UPDATE (Tính năng 1 + 4) """
        nodes_list, health_status = get_system_status()
        log_messages = []
        message = ""
        message_type = "success"
        
        try:
            doc_id = request.form['doc_id']
            new_city = request.form['new_city']
            
            if not doc_id or not new_city:
                raise ValueError("Thiếu ID hoặc tên Thành phố mới")
                
            User = Query()
            payload = {"_id": doc_id, "data": {"city": new_city}}
            
            # 1. Cập nhật trên Leader
            updated_count = db.update(payload['data'], User._id == doc_id)
            if updated_count == 0:
                raise ValueError(f"Không tìm thấy bản ghi có ID {doc_id} trên Leader.")
            
            log_messages.append(f"LEADER: Đã cập nhật bản ghi {doc_id[:8]}... thành phố = {new_city}.")
            
            # 2. Phát tán
            broadcast_request('replicate_update', payload, log_messages, health_status)
            message = f"Thành công: Đã cập nhật bản ghi {doc_id[:8]}..."
            
        except Exception as e:
            message = f"Lỗi: {str(e)}"
            message_type = "error"
            log_messages.append(f"Lỗi nghiêm trọng khi cập nhật: {e}")

        return render_template('index.html', 
                               results=None, 
                               message=message, 
                               message_type=message_type, 
                               nodes=nodes_list,
                               log_messages=log_messages)

    # --- 1. API MỚI: DELETE ---
    @app.route('/delete', methods=['POST'])
    def delete():
        """ Xử lý yêu cầu DELETE (Tính năng 1 + 4) """
        nodes_list, health_status = get_system_status()
        log_messages = []
        message = ""
        message_type = "success"
        
        try:
            doc_id = request.form['doc_id']
            if not doc_id:
                raise ValueError("Thiếu ID")

            User = Query()
            payload = {"_id": doc_id}
            
            # 1. Xóa trên Leader
            removed_count = db.remove(User._id == doc_id)
            if removed_count == 0:
                 raise ValueError(f"Không tìm thấy bản ghi có ID {doc_id} trên Leader.")
            
            log_messages.append(f"LEADER: Đã xóa bản ghi {doc_id[:8]}...")
            
            # 2. Phát tán
            broadcast_request('replicate_delete', payload, log_messages, health_status)
            message = f"Thành công: Đã xóa bản ghi {doc_id[:8]}..."
            
        except Exception as e:
            message = f"Lỗi: {str(e)}"
            message_type = "error"
            log_messages.append(f"Lỗi nghiêm trọng khi xóa: {e}")

        return render_template('index.html', 
                               results=None, 
                               message=message, 
                               message_type=message_type, 
                               nodes=nodes_list,
                               log_messages=log_messages)

    @app.route('/search', methods=['POST'])
    def search():
        """ Xử lý yêu cầu SEARCH (Tính năng 4) """
        nodes_list, health_status = get_system_status()
        log_messages = [] # 4. Khởi tạo list log
        all_results = []
        message = ""
        message_type = "success"
        
        try:
            search_payload = {
                "name": request.form.get('name', ''),
                "age": request.form.get('age', ''),
                "city": request.form.get('city', '')
            }
            if not any(search_payload.values()):
                raise ValueError("Bạn phải nhập ít nhất một điều kiện tìm kiếm.")
            
            log_messages.append(f"SCATTER: Bắt đầu truy vấn song song (Query: {search_payload})")
            
            futures_map = {}
            online_followers = [url for url in FOLLOWER_URLS if health_status.get(url) == "Online"]

            # 2. SCATTER (chỉ tới các Follower online)
            def fetch_search(url):
                try:
                    res = requests.post(f"{url}/local_search", json=search_payload, timeout=3)
                    if res.status_code == 200:
                        return res.json()
                except Exception as e:
                    print(f"Leader lỗi khi truy vấn {url}: {e}")
                return [] 

            for url in online_followers:
                future = executor.submit(fetch_search, url)
                futures_map[future] = url
            
            # 3. Bao gồm cả Leader
            leader_name = app.config['LEADER_NAME']
            local_results = perform_search(db, search_payload)
            for res in local_results:
                res['source_node'] = leader_name
            all_results.extend(local_results)
            log_messages.append(f"GATHER: {leader_name} tìm thấy {len(local_results)} kết quả.")

            # 4. GATHER
            for future in futures_map:
                url = futures_map[future]
                node_name = app.config['NODE_MAP'][url]
                try:
                    follower_results = future.result()
                    for res in follower_results:
                        res['source_node'] = node_name
                    all_results.extend(follower_results)
                    log_messages.append(f"GATHER: Nhận {len(follower_results)} kết quả từ {node_name}.")
                except Exception as e:
                     log_messages.append(f"GATHER: Lỗi khi lấy kết quả từ {node_name}: {e}")
            
            log_messages.append(f"AGGREGATE: Tổng hợp {len(all_results)} kết quả.")
            message = f"Truy vấn tìm thấy tổng cộng {len(all_results)} kết quả."
        
        except Exception as e:
            message = f"Lỗi: {str(e)}"
            message_type = "error"
            log_messages.append(f"Lỗi nghiêm trọng khi tìm kiếm: {e}")
        
        return render_template('index.html', 
                               results=all_results, 
                               message=message, 
                               message_type=message_type, 
                               nodes=nodes_list,
                               log_messages=log_messages) # 4. Truyền log ra

    # --- API nội bộ ---
    
    @app.route('/local_search', methods=['POST'])
    def local_search_api():
        data = request.get_json()
        results = perform_search(db, data)
        return jsonify(results), 200
            
    # --- 2. API HEALTH CHECK CHO LEADER ---
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({"status": "ok"}), 200
            
    return app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Leader node.')
    parser.add_argument('--port', type=int, required=True, help='Port to run on.')
    parser.add_argument('--db', type=str, required=True, help='Path to TinyDB file.')
    parser.add_argument('--followers', type=str, required=True, help='Comma-separated list of follower URLs.')
    args = parser.parse_args()
    
    follower_list = args.followers.split(',')
    app = create_app(args.db, follower_list, args.port)
    app.run(port=args.port, debug=True, use_reloader=False)