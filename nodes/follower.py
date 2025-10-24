# nodes/follower.py
import argparse
from flask import Flask, request, jsonify
from tinydb import TinyDB, Query, where
import os

db = None # Sẽ được khởi tạo trong create_app

# --- Logic tìm kiếm (sao chép từ leader.py) ---
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

def create_app(db_path):
    app = Flask(__name__)
    global db
    
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = TinyDB(db_path)
    app.config['DB_PATH'] = db_path

    # --- 1. Đổi tên API từ /replicate -> /replicate_insert ---
    @app.route('/replicate_insert', methods=['POST'])
    def replicate_insert():
        data = request.get_json()
        try:
            doc = data.get('document')
            if doc and '_id' in doc:
                db.insert(doc)
                print(f"Follower (DB: {app.config['DB_PATH']}) đã sao chép (INSERT): {doc.get('name')}")
                return jsonify({"status": "success"}), 200
            else:
                return jsonify({"status": "error", "message": "No document or _id provided"}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # --- 1. API MỚI: REPLICATE_UPDATE ---
    @app.route('/replicate_update', methods=['POST'])
    def replicate_update():
        data = request.get_json()
        try:
            doc_id = data.get('_id')
            update_data = data.get('data')
            if not doc_id or not update_data:
                return jsonify({"status": "error", "message": "Missing _id or data"}), 400
            
            User = Query()
            updated_count = db.update(update_data, User._id == doc_id)
            if updated_count > 0:
                print(f"Follower (DB: {app.config['DB_PATH']}) đã sao chép (UPDATE): {doc_id[:8]}...")
                return jsonify({"status": "success"}), 200
            else:
                print(f"Follower (DB: {app.config['DB_PATH']}) không tìm thấy bản ghi (UPDATE): {doc_id[:8]}...")
                return jsonify({"status": "not_found"}), 404
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # --- 1. API MỚI: REPLICATE_DELETE ---
    @app.route('/replicate_delete', methods=['POST'])
    def replicate_delete():
        data = request.get_json()
        try:
            doc_id = data.get('_id')
            if not doc_id:
                return jsonify({"status": "error", "message": "Missing _id"}), 400
            
            User = Query()
            removed_count = db.remove(User._id == doc_id)
            if removed_count > 0:
                print(f"Follower (DB: {app.config['DB_PATH']}) đã sao chép (DELETE): {doc_id[:8]}...")
                return jsonify({"status": "success"}), 200
            else:
                print(f"Follower (DB: {app.config['DB_PATH']}) không tìm thấy bản ghi (DELETE): {doc_id[:8]}...")
                return jsonify({"status": "not_found"}), 404
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/local_search', methods=['POST'])
    def local_search():
        data = request.get_json()
        try:
            results = perform_search(db, data)
            print(f"Follower (DB: {app.config['DB_PATH']}) tìm thấy {len(results)} kết quả")
            return jsonify(results), 200
        except Exception as e:
            print(f"Follower (DB: {app.config['DB_PATH']}) lỗi tìm kiếm: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # --- 2. API MỚI: HEALTH CHECK ---
    @app.route('/health', methods=['GET'])
    def health_check():
        """
        API đơn giản để Leader kiểm tra xem nút này còn 'sống' hay không.
        """
        return jsonify({"status": "ok"}), 200

    return app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a Follower node.')
    parser.add_argument('--port', type=int, required=True, help='Port to run on.')
    parser.add_argument('--db', type=str, required=True, help='Path to TinyDB file.')
    args = parser.parse_args()
    
    app = create_app(args.db)
    app.run(port=args.port, debug=True, use_reloader=False)