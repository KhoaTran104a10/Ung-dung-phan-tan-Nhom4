# follower.py
# Đóng vai trò là Worker/Follower Node

import os
import argparse
from flask import Flask, request, jsonify
from flask_cors import CORS
from tinydb import TinyDB, Query

app = Flask(__name__)
CORS(app)

parser = argparse.ArgumentParser(description='Chạy một Follower Node.')
parser.add_argument('--port', type=int, required=True, help='Cổng để chạy follower.')
parser.add_argument('--dbfile', type=str, required=True, help='Tên file database cho follower này.')
args = parser.parse_args()

# Khởi tạo instance TinyDB cho Follower
db = TinyDB(args.dbfile)

@app.route('/replicate', methods=['POST'])
def handle_replicate():
    """API nội bộ để Leader gọi và sao chép dữ liệu."""
    data = request.get_json()
    if not data or 'document' not in data:
        return jsonify({"error": "Dữ liệu không hợp lệ"}), 400
    
    document = data['document']
    try:
        db.insert(document)
        print(f"Follower@{args.port}: Đã sao chép: {document}")
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/local_search', methods=['POST'])
def handle_local_search():
    """API nội bộ để Coordinator gọi và thực hiện truy vấn cục bộ."""
    query_info = request.get_json()
    if not query_info or 'query' not in query_info:
        return jsonify({"error": "Truy vấn không hợp lệ"}), 400
        
    query_data = query_info['query']
    User = Query()
    
    key, op, value = query_data['key'], query_data['op'], query_data['value']
    
    ops = {'>': lambda k, v: k > v, '<': lambda k, v: k < v, '==': lambda k, v: k == v}
    if op in ops:
        results = db.search(ops[op](User[key], value))
        print(f"Follower@{args.port}: Tìm thấy {len(results)} kết quả.")
        return jsonify({"results": results})
    
    return jsonify({"results": []})

@app.route('/shutdown', methods=['POST'])
def shutdown():
    """Endpoint để dừng Flask server."""
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    return 'Server shutting down...'

if __name__ == '__main__':
    if os.path.exists(args.dbfile):
        os.remove(args.dbfile)
    print(f"Follower node đang chạy trên cổng {args.port} với file DB '{args.dbfile}'...")
    app.run(port=args.port, debug=False)

