# nodes/leader.py
import argparse
import requests
from flask import Flask, request, jsonify, render_template
from tinydb import TinyDB, Query, where
from concurrent.futures import ThreadPoolExecutor
import os

db = None
FOLLOWER_URLS = []
executor = ThreadPoolExecutor(max_workers=10)

# --- Logic tìm kiếm (dùng chung) ---
def perform_search(db_instance, data):
    """
    Hàm logic tìm kiếm nâng cao, lọc theo các trường được cung cấp.
    Thực hiện tìm kiếm 'AND'.
    """
    try:
        search_name = data.get('name', '').strip()
        search_age = data.get('age', '').strip()
        search_city = data.get('city', '').strip()

        User = Query()
        conditions = [] # Danh sách các điều kiện lọc

        if search_name:
            # Dùng 'test' để tìm kiếm (case-insensitive contains)
            conditions.append(where('name').test(lambda s: search_name.lower() in s.lower()))
        
        if search_age:
            # Dùng '==' vì tuổi là số chính xác
            try:
                conditions.append(User.age == int(search_age))
            except ValueError:
                pass # Bỏ qua nếu tuổi không phải là số
        
        if search_city:
            conditions.append(where('city').test(lambda s: search_city.lower() in s.lower()))
        
        if not conditions:
            # Nếu không có điều kiện nào, không trả về gì cả
            return []

        # Xây dựng truy vấn 'AND' từ tất cả các điều kiện
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
    
    app.config['DB_PATH'] = db_path
    app.config['LEADER_PORT'] = leader_port
    
    # Tạo một bản đồ (map) các Node để gắn thẻ kết quả
    app.config['NODE_MAP'] = {}
    app.config['LEADER_NAME'] = f"Leader ({leader_port})"
    # Tự thêm mình vào map
    app.config['NODE_MAP'][f"http://127.0.0.1:{leader_port}"] = app.config['LEADER_NAME']
    # Thêm các follower
    for i, url in enumerate(FOLLOWER_URLS):
        port = url.split(':')[-1]
        app.config['NODE_MAP'][url] = f"Follower {i+1} ({port})"

    # --- Các hàm xử lý nội bộ ---

    def broadcast_replication(doc):
        payload = {"document": doc}
        def post_request(url):
            try:
                requests.post(f"{url}/replicate", json=payload, timeout=2)
                print(f"Leader đã gửi sao chép tới {url}")
            except Exception as e:
                print(f"Leader lỗi khi sao chép tới {url}: {e}")

        for url in FOLLOWER_URLS:
            executor.submit(post_request, url)
        print(f"Leader đã bắt đầu sao chép '{doc.get('name')}' tới {len(FOLLOWER_URLS)} followers.")

    def local_search_logic(data):
        """ Hàm logic truy vấn cục bộ, gọi hàm perform_search """
        return perform_search(db, data)

    # --- API cho Giao diện Web (Client) ---

    @app.route('/')
    def index():
        """ Hiển thị trang web chính. """
        nodes_list = []
        leader_url = f"http://127.0.0.1:{app.config['LEADER_PORT']}"
        nodes_list.append({"url": leader_url, "role": app.config['LEADER_NAME']})
        
        for url in FOLLOWER_URLS:
            nodes_list.append({"url": url, "role": app.config['NODE_MAP'][url]})
            
        return render_template('index.html', results=None, message=None, nodes=nodes_list)

    @app.route('/insert', methods=['POST'])
    def insert():
        """ Xử lý yêu cầu INSERT từ client. """
        message = ""
        message_type = "success"
        try:
            name = request.form['name']
            age = int(request.form['age'])
            city = request.form['city']
            doc = {'name': name, 'age': age, 'city': city}
            
            db.insert(doc)
            print(f"Leader (DB: {app.config['DB_PATH']}) đã chèn: {name}")
            broadcast_replication(doc)
            
            message = f"Thành công: Đã chèn '{name}' vào Leader và gửi lệnh sao chép."
        except Exception as e:
            message = f"Lỗi: {str(e)}"
            message_type = "error"
            
        # Tải lại danh sách node
        nodes_list = []
        leader_url = f"http://127.0.0.1:{app.config['LEADER_PORT']}"
        nodes_list.append({"url": leader_url, "role": app.config['LEADER_NAME']})
        for url in FOLLOWER_URLS:
            nodes_list.append({"url": url, "role": app.config['NODE_MAP'][url]})
        
        return render_template('index.html', results=None, message=message, message_type=message_type, nodes=nodes_list)

    @app.route('/search', methods=['POST'])
    def search():
        """
        Xử lý yêu cầu SEARCH (Scatter-Gather).
        *** CẬP NHẬT: Gắn thẻ nguồn (source_node) vào kết quả ***
        """
        all_results = []
        message = ""
        message_type = "success"
        
        try:
            # 1. Lấy tất cả các tham số tìm kiếm từ form
            search_payload = {
                "name": request.form.get('name', ''),
                "age": request.form.get('age', ''),
                "city": request.form.get('city', '')
            }
            
            # Nếu tất cả đều rỗng, không tìm gì cả
            if not any(search_payload.values()):
                raise ValueError("Bạn phải nhập ít nhất một điều kiện tìm kiếm.")

            futures_map = {} # {future: url}
            
            # 2. SCATTER: Gửi yêu cầu tìm kiếm song song đến tất cả Follower
            def fetch_search(url):
                try:
                    res = requests.post(f"{url}/local_search", json=search_payload, timeout=3)
                    if res.status_code == 200:
                        return res.json() # Chỉ trả về dữ liệu thô
                except Exception as e:
                    print(f"Leader lỗi khi truy vấn {url}: {e}")
                return [] 

            for url in FOLLOWER_URLS:
                future = executor.submit(fetch_search, url)
                futures_map[future] = url
            
            # 3. Bao gồm cả Leader (chính nó) vào quá trình tìm kiếm
            leader_name = app.config['LEADER_NAME']
            local_results = local_search_logic(search_payload)
            # Gắn thẻ nguồn cho kết quả của Leader
            for res in local_results:
                res['source_node'] = leader_name
            all_results.extend(local_results)
            print(f"{leader_name} tìm thấy {len(local_results)} kết quả")

            # 4. GATHER: Thu thập kết quả từ các Follower
            for future in futures_map:
                url = futures_map[future]
                node_name = app.config['NODE_MAP'][url] # Lấy tên Node từ map
                try:
                    follower_results = future.result()
                    # Gắn thẻ nguồn cho kết quả của Follower
                    for res in follower_results:
                        res['source_node'] = node_name
                    all_results.extend(follower_results)
                    print(f"Leader đã nhận {len(follower_results)} kết quả từ {node_name}")
                except Exception as e:
                     print(f"Lỗi khi lấy kết quả từ {url}: {e}")

            message = f"Truy vấn tìm thấy tổng cộng {len(all_results)} kết quả từ tất cả các nút."
        
        except Exception as e:
            message = f"Lỗi: {str(e)}"
            message_type = "error"
        
        # Tải lại danh sách node
        nodes_list = []
        leader_url = f"http://127.0.0.1:{app.config['LEADER_PORT']}"
        nodes_list.append({"url": leader_url, "role": app.config['LEADER_NAME']})
        for url in FOLLOWER_URLS:
            nodes_list.append({"url": url, "role": app.config['NODE_MAP'][url]})

        return render_template('index.html', results=all_results, message=message, message_type=message_type, nodes=nodes_list)

    # --- API nội bộ ---
    
    @app.route('/local_search', methods=['POST'])
    def local_search_api():
        data = request.get_json()
        results = local_search_logic(data)
        return jsonify(results), 200
            
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