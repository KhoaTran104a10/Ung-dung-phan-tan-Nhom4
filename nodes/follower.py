# nodes/follower.py
import argparse
from flask import Flask, request, jsonify
from tinydb import TinyDB, Query, where
import os

db = None # Sẽ được khởi tạo trong create_app

# --- Logic tìm kiếm (sao chép từ leader.py) ---
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

        final_condition = conditions.pop(0)
        for cond in conditions:
            final_condition = (final_condition & cond)
            
        return db_instance.search(final_condition)
        
    except Exception as e:
        print(f"Lỗi khi thực hiện tìm kiếm: {e}")
        return []
# ------------------------------------

def create_app(db_path):
    app = Flask(__name__)
    global db
    
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = TinyDB(db_path)
    app.config['DB_PATH'] = db_path

    @app.route('/replicate', methods=['POST'])
    def replicate():
        data = request.get_json()
        try:
            doc = data.get('document')
            if doc:
                db.insert(doc)
                print(f"Follower (DB: {app.config['DB_PATH']}) đã sao chép: {doc.get('name')}")
                return jsonify({"status": "success"}), 200
            else:
                return jsonify({"status": "error", "message": "No document provided"}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/local_search', methods=['POST'])
    def local_search():
        """
        API nội bộ: Thực hiện truy vấn nâng cao
        *** CẬP NHẬT: Sử dụng hàm perform_search ***
        """
        data = request.get_json()
        try:
            results = perform_search(db, data)
            print(f"Follower (DB: {app.config['DB_PATH']}) tìm thấy {len(results)} kết quả")
            return jsonify(results), 200
        except Exception as e:
            print(f"Follower (DB: {app.config['DB_PATH']}) lỗi tìm kiếm: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    return app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a Follower node.')
    parser.add_argument('--port', type=int, required=True, help='Port to run on.')
    parser.add_argument('--db', type=str, required=True, help='Path to TinyDB file.')
    args = parser.parse_args()
    
    app = create_app(args.db)
    app.run(port=args.port, debug=True, use_reloader=False)