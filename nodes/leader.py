# nodes/leader.py
import argparse
import requests
import uuid
from flask import Flask, request, jsonify, render_template
from tinydb import TinyDB, Query, where
from concurrent.futures import ThreadPoolExecutor
import os

# Biến toàn cục
db = None
FOLLOWER_URLS = []
executor = ThreadPoolExecutor(max_workers=10)

# ---------------------------
# HÀM PHỤ TRỢ
# ---------------------------
def perform_search(db_instance, data):
    """
    Hàm tìm kiếm dữ liệu trong TinyDB dựa theo name, age, city.
    Dùng chung cho cả Leader và Follower.
    """
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
            except ValueError:
                pass
        if search_city:
            conditions.append(where('city').test(lambda s: search_city.lower() in s.lower()))

        if not conditions:
            return []

        # Kết hợp các điều kiện bằng toán tử AND
        final_condition = conditions.pop(0)
        for cond in conditions:
            final_condition &= cond

        return db_instance.search(final_condition)
    except Exception as e:
        print(f"Lỗi khi tìm kiếm: {e}")
        return []

# ---------------------------
# KHỞI TẠO ỨNG DỤNG LEADER
# ---------------------------
def create_app(db_path, followers_list, leader_port):
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    
    global db, FOLLOWER_URLS
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = TinyDB(db_path)
    FOLLOWER_URLS = followers_list
    
    app.config['LEADER_PORT'] = leader_port
    app.config['LEADER_NAME'] = f"Leader ({leader_port})"
    
    # Bản đồ node (Leader + Followers)
    app.config['NODE_MAP'] = {}
    app.config['NODE_MAP'][f"http://127.0.0.1:{leader_port}"] = app.config['LEADER_NAME']
    for i, url in enumerate(FOLLOWER_URLS):
        port = url.split(':')[-1]
        app.config['NODE_MAP'][url] = f"Follower {i+1} ({port})"

    # ---------------------------
    # 1️.HÀM KIỂM TRA SỨC KHỎE CÁC NÚT
    # ---------------------------
    def get_system_status():
        """
        Trả về danh sách trạng thái (Online/Offline) của Leader và Followers.
        """
        nodes_list = []
        health_status = {}

        # Leader luôn online
        leader_url = f"http://127.0.0.1:{app.config['LEADER_PORT']}"
        nodes_list.append({"url": leader_url, "role": app.config['LEADER_NAME'], "status": "Online"})
        health_status[app.config['LEADER_NAME']] = "Online" # Sử dụng tên làm key

        # Kiểm tra Followers
        for url in FOLLOWER_URLS:
            node_name = app.config['NODE_MAP'][url]
            try:
                response = requests.get(f"{url}/health", timeout=0.5)
                if response.status_code == 200:
                    nodes_list.append({"url": url, "role": node_name, "status": "Online"})
                    health_status[url] = "Online" # Sử dụng URL làm key cho follower
                else:
                    nodes_list.append({"url": url, "role": node_name, "status": "Offline"})
                    health_status[url] = "Offline"
            except requests.ConnectionError:
                nodes_list.append({"url": url, "role": node_name, "status": "Offline"})
                health_status[url] = "Offline"
        
        return nodes_list, health_status

    # ---------------------------
    # 2️.HÀM SAO CHÉP DỮ LIỆU (Broadcast)
    # ---------------------------
    def broadcast_request(endpoint, payload, log_messages, health_status):
        """
        Gửi yêu cầu insert/update/delete đến các Followers đang online.
        """
        online_followers = [url for url in FOLLOWER_URLS if health_status.get(url) == "Online"]
        
        def post_request(url):
            try:
                requests.post(f"{url}/{endpoint}", json=payload, timeout=2)
                return f"Gửi {endpoint} tới {app.config['NODE_MAP'][url]} thành công."
            except Exception as e:
                return f"Lỗi gửi {endpoint} tới {app.config['NODE_MAP'][url]}: {e}"

        log_messages.append(f"Bắt đầu sao chép tới {len(online_followers)} Follower đang Online...")
        futures = [executor.submit(post_request, url) for url in online_followers]
        for future in futures:
            log_messages.append(future.result())

    # ---------------------------
    # ⭐ HÀM HELPER MỚI: LOGIC TÌM KIẾM TÁI SỬ DỤNG
    # ---------------------------
    def _perform_scatter_gather_search(search_payload, log_messages, health_status):
        """
        Hàm nội bộ thực hiện logic Scatter-Gather.
        Trả về (all_results, message, message_type)
        """
        all_results = []
        try:
            if not any(search_payload.values()):
                raise ValueError("Nhập ít nhất một điều kiện tìm kiếm.")
            
            log_messages.append(f"SCATTER: Truy vấn song song {search_payload}")
            futures_map = {}
            online_followers = [url for url in FOLLOWER_URLS if health_status.get(url) == "Online"]

            # Gửi truy vấn song song đến các Follower
            def fetch_search(url):
                try:
                    res = requests.post(f"{url}/local_search", json=search_payload, timeout=3)
                    return res.json() if res.status_code == 200 else []
                except Exception:
                    return []

            for url in online_followers:
                futures_map[executor.submit(fetch_search, url)] = url

            # Truy vấn local (Leader)
            leader_name = app.config['LEADER_NAME']
            local_results = perform_search(db, search_payload)
            for r in local_results:
                r['source_node'] = leader_name
            all_results.extend(local_results)
            log_messages.append(f"GATHER: {leader_name} có {len(local_results)} kết quả.")

            # Nhận kết quả từ các Follower
            for future in futures_map:
                url = futures_map[future]
                node_name = app.config['NODE_MAP'][url]
                results = future.result()
                for r in results:
                    r['source_node'] = node_name
                all_results.extend(results)
                log_messages.append(f"GATHER: {node_name} có {len(results)} kết quả.")

            log_messages.append(f"AGGREGATE: Tổng cộng {len(all_results)} kết quả.")
            message = f"Tìm thấy {len(all_results)} kết quả."
            return all_results, message, "success"
        
        except Exception as e:
            message = f"Lỗi: {e}"
            log_messages.append(f"Lỗi khi tìm kiếm: {e}")
            return [], message, "error"

    # ---------------------------
    # 3️.GIAO DIỆN WEB
    # ---------------------------
    @app.route('/')
    def index():
        """Trang dashboard chính."""
        nodes_list, _ = get_system_status()
        return render_template('index.html',
                               results=None, message=None,
                               nodes=nodes_list, log_messages=None,
                               last_search=None) # Thêm last_search=None

    # ---------------------------
    # 4️.API: INSERT
    # ---------------------------
    @app.route('/insert', methods=['POST'])
    def insert():
        # (Không thay đổi, vẫn render results=None sau khi Chèn)
        nodes_list, health_status = get_system_status()
        log_messages = []
        message = ""
        message_type = "success"
        
        try:
            name = request.form['name']
            age = int(request.form['age'])
            city = request.form['city']

            doc = {'_id': str(uuid.uuid4()), 'name': name, 'age': age, 'city': city}
            db.insert(doc)
            log_messages.append(f"LEADER: Đã chèn '{name}' (ID: {doc['_id'][:8]}...)")

            broadcast_request('replicate_insert', {"document": doc}, log_messages, health_status)
            message = f"Thành công: Đã chèn '{name}'."
        except Exception as e:
            message = f"Lỗi: {e}"
            message_type = "error"
            log_messages.append(f"Lỗi khi chèn: {e}")
        
        return render_template('index.html', results=None, message=message,
                               message_type=message_type, nodes=nodes_list,
                               log_messages=log_messages, last_search=None)

    # ---------------------------
    # 5️.API: UPDATE (CẬP NHẬT)
    # ---------------------------
    @app.route('/update', methods=['POST'])
    def update():
        """ 
        Xử lý yêu cầu UPDATE và TẢI LẠI KẾT QUẢ TÌM KIẾM.
        """
        nodes_list, health_status = get_system_status()
        log_messages = []
        message = ""
        message_type = "success"
        all_results = None     # Mặc định là None
        last_search_payload = None # Mặc định là None
        
        try:
            # 1. THỰC HIỆN CẬP NHẬT
            doc_id = request.form['doc_id']
            new_name = request.form['name']
            new_age = int(request.form['age']) 
            new_city = request.form['city']
            
            if not doc_id or not new_name or not new_city: 
                raise ValueError("Thiếu thông tin cập nhật (ID, Tên, Tuổi, Thành phố)")
                
            User = Query()
            update_data = {"name": new_name, "age": new_age, "city": new_city}
            payload = {"_id": doc_id, "data": update_data}
            
            updated_count = db.update(update_data, User._id == doc_id)
            if updated_count == 0:
                raise ValueError(f"Không tìm thấy bản ghi có ID {doc_id} trên Leader.")
            
            log_messages.append(f"LEADER: Đã cập nhật bản ghi {doc_id[:8]}... (Tên={new_name}, Tuổi={new_age}, TP={new_city}).")
            broadcast_request('replicate_update', payload, log_messages, health_status)
            message = f"Thành công: Đã cập nhật bản ghi {doc_id[:8]}..."
            
            # 2. KIỂM TRA VÀ TÌM KIẾM LẠI
            last_search_name = request.form.get('last_search_name')
            last_search_age = request.form.get('last_search_age')
            last_search_city = request.form.get('last_search_city')

            # Nếu có thông tin tìm kiếm cũ (do JS gửi lên)
            if last_search_name is not None and last_search_age is not None and last_search_city is not None:
                last_search_payload = {
                    "name": last_search_name,
                    "age": last_search_age,
                    "city": last_search_city
                }
                # Chỉ tìm lại nếu có ít nhất 1 tiêu chí
                if any(v for v in last_search_payload.values() if v):
                    log_messages.append("---")
                    log_messages.append("Tự động tải lại kết quả tìm kiếm...")
                    all_results, search_msg, search_msg_type = _perform_scatter_gather_search(
                        last_search_payload, log_messages, health_status
                    )
                    message += f" | {search_msg}"
                    if search_msg_type == "error":
                        message_type = "error"

        except Exception as e:
            message = f"Lỗi: {str(e)}"
            message_type = "error"
            log_messages.append(f"Lỗi nghiêm trọng khi cập nhật: {e}")

        return render_template('index.html', 
                               results=all_results,         # Trả về kết quả mới
                               message=message, 
                               message_type=message_type, 
                               nodes=nodes_list,
                               log_messages=log_messages,
                               last_search=last_search_payload) # Trả về tiêu chí cũ

    # ---------------------------
    # 6️.API: DELETE (CẬP NHẬT)
    # ---------------------------
    @app.route('/delete', methods=['POST'])
    def delete():
        """ 
        Xử lý yêu cầu DELETE và TẢI LẠI KẾT QUẢ TÌM KIẾM.
        """
        nodes_list, health_status = get_system_status()
        log_messages = []
        message = ""
        message_type = "success"
        all_results = None     # Mặc định là None
        last_search_payload = None # Mặc định là None

        try:
            # 1. THỰC HIỆN XÓA
            doc_id = request.form['doc_id']
            if not doc_id:
                raise ValueError("Thiếu ID")

            User = Query()
            removed = db.remove(User._id == doc_id)
            if not removed: # db.remove trả về list các ID đã xóa
                raise ValueError(f"Không tìm thấy bản ghi {doc_id}")

            log_messages.append(f"LEADER: Đã xóa bản ghi {doc_id[:8]}...")
            broadcast_request('replicate_delete', {"_id": doc_id}, log_messages, health_status)
            message = f"Thành công: Đã xóa bản ghi {doc_id[:8]}..."

            # 2. KIỂM TRA VÀ TÌM KIẾM LẠI
            last_search_name = request.form.get('last_search_name')
            last_search_age = request.form.get('last_search_age')
            last_search_city = request.form.get('last_search_city')

            if last_search_name is not None and last_search_age is not None and last_search_city is not None:
                last_search_payload = {
                    "name": last_search_name,
                    "age": last_search_age,
                    "city": last_search_city
                }
                if any(v for v in last_search_payload.values() if v):
                    log_messages.append("---")
                    log_messages.append("Tự động tải lại kết quả tìm kiếm...")
                    all_results, search_msg, search_msg_type = _perform_scatter_gather_search(
                        last_search_payload, log_messages, health_status
                    )
                    message += f" | {search_msg}"
                    if search_msg_type == "error":
                        message_type = "error"

        except Exception as e:
            message = f"Lỗi: {e}"
            message_type = "error"
            log_messages.append(f"Lỗi khi xóa: {e}")

        return render_template('index.html', 
                               results=all_results,         # Trả về kết quả mới
                               message=message,
                               message_type=message_type, 
                               nodes=nodes_list,
                               log_messages=log_messages,
                               last_search=last_search_payload) # Trả về tiêu chí cũ

    # ---------------------------
    # 7️.API: SEARCH (CẬP NHẬT)
    # ---------------------------
    @app.route('/search', methods=['POST'])
    def search():
        """
        Hàm SEARCH chính, giờ chỉ gọi hàm helper.
        """
        nodes_list, health_status = get_system_status()
        log_messages = []
        
        search_payload = {
            "name": request.form.get('name', ''),
            "age": request.form.get('age', ''),
            "city": request.form.get('city', '')
        }
        
        # Gọi hàm helper
        all_results, message, message_type = _perform_scatter_gather_search(
            search_payload, log_messages, health_status
        )

        return render_template('index.html', 
                               results=all_results, 
                               message=message,
                               message_type=message_type, 
                               nodes=nodes_list,
                               log_messages=log_messages,
                               last_search=search_payload) # Trả về tiêu chí tìm kiếm

    # ---------------------------
    # 8️.API NỘI BỘ
    # ---------------------------
    @app.route('/local_search', methods=['POST'])
    def local_search_api():
        data = request.get_json()
        results = perform_search(db, data)
        return jsonify(results), 200
            
    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({"status": "ok"}), 200
            
    return app


# ---------------------------
# CHẠY CHƯƠNG TRÌNH CHÍNH
# ---------------------------
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Leader node.')
    
    # SỬA 3 DÒNG NÀY:
    parser.add_argument('--port', type=int, required=True, help='Port để chạy.')
    parser.add_argument('--db', type=str, required=True, help='Đường dẫn file TinyDB.')
    parser.add_argument('--followers', type=str, required=True, help='Danh sách URL của Followers (phân cách bởi dấu phẩy).')
    
    args = parser.parse_args()
    
    follower_list = args.followers.split(',')
    
    # Sửa lỗi: Đảm bảo thư mục 'data' tồn tại trước khi tạo app
    db_dir = os.path.dirname(args.db)
    if db_dir: # Nếu có chỉ định thư mục (vd: 'data/leader_db.json')
        os.makedirs(db_dir, exist_ok=True)

    app = create_app(args.db, follower_list, args.port)
    app.run(port=args.port, debug=True, use_reloader=False)