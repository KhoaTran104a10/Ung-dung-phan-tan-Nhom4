# nodes/follower.py
import argparse
from flask import Flask, request, jsonify
from tinydb import TinyDB, Query, where
import os

# Biến toàn cục lưu cơ sở dữ liệu
db = None  

# ===============================
# HÀM TÌM KIẾM (dùng chung với Leader)
# ===============================
def perform_search(db_instance, data):
    """
    Thực hiện tìm kiếm trong cơ sở dữ liệu TinyDB dựa theo:
    - name (chuỗi con, không phân biệt hoa/thường)
    - age (số nguyên)
    - city (chuỗi con, không phân biệt hoa/thường)
    """
    try:
        search_name = data.get('name', '').strip()
        search_age = data.get('age', '').strip()
        search_city = data.get('city', '').strip()
        User = Query()
        conditions = []

        # Xây dựng điều kiện tìm kiếm
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

        # Kết hợp các điều kiện bằng AND
        final_condition = conditions.pop(0)
        for cond in conditions:
            final_condition &= cond

        return db_instance.search(final_condition)
    except Exception as e:
        print(f"Lỗi khi thực hiện tìm kiếm: {e}")
        return []

# ===============================
# KHỞI TẠO ỨNG DỤNG FOLLOWER
# ===============================
def create_app(db_path):
    app = Flask(__name__)
    global db

    # Đảm bảo thư mục chứa file DB tồn tại
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db = TinyDB(db_path)
    app.config['DB_PATH'] = db_path

    # ------------------------------------
    # 1️⃣ API: REPLICATE_INSERT
    # ------------------------------------
    @app.route('/replicate_insert', methods=['POST'])
    def replicate_insert():
        """
        Nhận bản sao dữ liệu từ Leader (INSERT)
        """
        data = request.get_json()
        try:
            doc = data.get('document')
            if doc and '_id' in doc:
                db.insert(doc)
                print(f"[Follower] Đã sao chép (INSERT): {doc.get('name')} vào {app.config['DB_PATH']}")
                return jsonify({"status": "success"}), 200
            return jsonify({"status": "error", "message": "Thiếu document hoặc _id"}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # ------------------------------------
    # 2️⃣ API: REPLICATE_UPDATE
    # ------------------------------------
    @app.route('/replicate_update', methods=['POST'])
    def replicate_update():
        """
        Nhận bản sao lệnh cập nhật từ Leader (UPDATE)
        """
        data = request.get_json()
        try:
            doc_id = data.get('_id')
            update_data = data.get('data')
            if not doc_id or not update_data:
                return jsonify({"status": "error", "message": "Thiếu _id hoặc data"}), 400

            User = Query()
            updated_count = db.update(update_data, User._id == doc_id)

            if updated_count > 0:
                print(f"[Follower] Đã sao chép (UPDATE): {doc_id[:8]}...")
                return jsonify({"status": "success"}), 200
            else:
                print(f"[Follower] Không tìm thấy bản ghi (UPDATE): {doc_id[:8]}...")
                return jsonify({"status": "not_found"}), 404
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # ------------------------------------
    # 3️⃣ API: REPLICATE_DELETE
    # ------------------------------------
    @app.route('/replicate_delete', methods=['POST'])
    def replicate_delete():
        """
        Nhận bản sao lệnh xóa từ Leader (DELETE)
        """
        data = request.get_json()
        try:
            doc_id = data.get('_id')
            if not doc_id:
                return jsonify({"status": "error", "message": "Thiếu _id"}), 400

            User = Query()
            removed_count = db.remove(User._id == doc_id)

            if removed_count > 0:
                print(f"[Follower] Đã sao chép (DELETE): {doc_id[:8]}...")
                return jsonify({"status": "success"}), 200
            else:
                print(f"[Follower] Không tìm thấy bản ghi (DELETE): {doc_id[:8]}...")
                return jsonify({"status": "not_found"}), 404
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # ------------------------------------
    # 4️⃣ API: LOCAL SEARCH
    # ------------------------------------
    @app.route('/local_search', methods=['POST'])
    def local_search():
        """
        Cho phép Leader gửi yêu cầu tìm kiếm nội bộ đến Follower
        """
        data = request.get_json()
        try:
            results = perform_search(db, data)
            print(f"[Follower] Tìm thấy {len(results)} kết quả trong {app.config['DB_PATH']}")
            return jsonify(results), 200
        except Exception as e:
            print(f"[Follower] Lỗi tìm kiếm: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    # ------------------------------------
    # 5️⃣ API: HEALTH CHECK
    # ------------------------------------
    @app.route('/health', methods=['GET'])
    def health_check():
        """
        API cho phép Leader kiểm tra tình trạng hoạt động của Follower
        """
        return jsonify({"status": "ok"}), 200

    return app

# ===============================
# CHẠY ỨNG DỤNG FOLLOWER
# ===============================
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run a Follower node.')
    parser.add_argument('--port', type=int, required=True, help='Cổng để chạy Follower.')
    parser.add_argument('--db', type=str, required=True, help='Đường dẫn file TinyDB.')
    args = parser.parse_args()

    app = create_app(args.db)
    app.run(port=args.port, debug=True, use_reloader=False)
