🚀 Prototype TinyDB Phân tán
Đây là dự án mô phỏng các tính năng cốt lõi của một hệ thống CSDL phân tán, sử dụng TinyDB (một CSDL NoSQL siêu nhẹ) làm nền tảng lưu trữ.

Mục tiêu của dự án là minh họa và thực hành các khái niệm phức tạp trong hệ thống phân tán (như sao chép, truy vấn song song, khả năng chịu lỗi) trên một nền tảng đơn giản, dễ hiểu mà không bị "choáng ngợp" bởi các hệ thống lớn như MongoDB hay Cassandra.

🌟 Tính năng chính
Sao chép Leader-Follower (CRUD):

Hỗ trợ đầy đủ INSERT, UPDATE, DELETE.

Mọi thao tác ghi (write) đều phải đi qua Leader và được sao chép đồng bộ đến các Follower.

Sử dụng _id (UUID) duy nhất để định danh bản ghi trên toàn hệ thống.

Truy vấn song song (Scatter-Gather):

Client gửi yêu cầu SEARCH đến Leader (đóng vai trò Coordinator).

Leader "phân tán" (scatter) truy vấn đến tất cả các nút (bao gồm cả chính nó).

Các nút tự tìm kiếm trên dữ liệu cục bộ và trả kết quả về.

Leader "thu thập" (gather) và tổng hợp tất cả kết quả trước khi trả về cho client.

Giao diện Dashboard (Web UI):

Giao diện web trực quan (viết bằng Flask) để thực hiện các thao tác CRUD và Tìm kiếm.

Kiểm tra sức khỏe (Health Check):

Leader tự động kiểm tra trạng thái "Online" / "Offline" của các Follower thông qua API /health.

Trạng thái được hiển thị trực tiếp trên UI (chấm xanh/đỏ).

Mô phỏng lỗi (Fault Tolerance Demo):

Cho phép người dùng chủ động "Tắt" một nút Follower ngay từ giao diện web.

Khi một nút bị tắt, Leader sẽ nhận diện nó là "Offline" và tự động bỏ qua nút đó khi sao chép dữ liệu mới, chứng minh khả năng chịu lỗi.

Nhật ký hoạt động (Live Logging):

Mọi hành động (Search, Insert, Replicate...) đều được ghi log và hiển thị trực quan trên UI, giúp người dùng hiểu rõ các bước đang diễn ra "bên dưới".

🛠️ Công nghệ sử dụng
Ngôn ngữ: Python 3

Thư viện:

Flask: Để tạo Web Server và API cho các nút.

TinyDB: CSDL NoSQL lưu trữ (dưới dạng file JSON).

Requests: Để giao tiếp (gọi API) giữa các nút.

📁 Cấu trúc thư mục
distributed_tinydb/
├── data/                 # Chứa các file .json của TinyDB
├── nodes/
│   ├── leader.py         # Logic của Nút Leader (Coordinator)
│   └── follower.py       # Logic của Nút Follower (Worker)
├── static/
│   └── style.css         # CSS cho giao diện
├── templates/
│   └── index.html        # Giao diện web
├── run.py                # Script chạy toàn bộ 3 nút (chỉ cho dev nhanh)
├── sample_data.py        # Script tạo dữ liệu mẫu ban đầu
├── requirements.txt      # Các thư viện cần thiết
└── README.md             # File này
⚙️ Cài đặt
Clone repository này về máy.

(Khuyến khích) Tạo một môi trường ảo:

Bash

python -m venv venv
Trên Windows: .\venv\Scripts\activate

Trên macOS/Linux: source venv/bin/activate

Cài đặt các thư viện cần thiết:

Bash

pip install -r requirements.txt
Chạy script để tạo dữ liệu mẫu ban đầu (dữ liệu này được phân tán sẵn để demo Scatter-Gather):

Bash

python sample_data.py
🚀 Hướng dẫn chạy (Quan trọng)
Để demo chính xác tính năng chịu lỗi (tắt một nút mà không làm sập các nút khác), bạn phải chạy thủ công 3 nút trên 3 cửa sổ Terminal (hoặc 3 tab) riêng biệt.

(Không dùng run.py để demo, vì nó sẽ tắt tất cả các nút khi một nút con bị lỗi).

🖥️ Terminal 1: Chạy Leader (Port 5000)
Bash

python nodes/leader.py --port=5000 --db=data/leader_db.json --followers=http://127.0.0.1:5001,http://127.0.0.1:5002
🖥️ Terminal 2: Chạy Follower 1 (Port 5001)
Bash

python nodes/follower.py --port=5001 --db=data/follower1_db.json
🖥️ Terminal 3: Chạy Follower 2 (Port 5002)
Bash

python nodes/follower.py --port=5002 --db=data/follower2_db.json
Sau khi cả 3 terminal đều chạy, mở trình duyệt và truy cập: http://127.0.0.1:5000

🧪 Kịch bản Demo
Đây là các kịch bản để kiểm thử đầy đủ các tính năng của hệ thống.

Kịch bản 1: Truy vấn song song (Scatter-Gather)
Mở http://127.0.0.1:5000.

Trong form "Tính năng 2", gõ chữ L vào ô "Thành phố (chứa)" (để tìm "London").

Nhấn "Tìm kiếm".

Kết quả: Bạn sẽ thấy 2 bản ghi (Charlie, David). Trong "Nhật ký hoạt động", bạn sẽ thấy log "GATHER" báo rằng Leader tìm thấy 0, Follower 1 tìm thấy 2, và Follower 2 tìm thấy 0. Điều này chứng minh hệ thống đã tìm kiếm song song trên dữ liệu phân tán.

Kịch bản 2: Sao chép CRUD (Leader-Follower)
Trong form "Tính năng 1", chèn một người dùng mới:

Tên: Grace

Tuổi: 40

Thành phố: Paris

Nhấn "Chèn".

Kết quả: "Nhật ký" sẽ hiển thị LEADER: Đã chèn, và 2 log Gửi sao chép tới Follower 1 và Follower 2.

Bây giờ, tìm kiếm Tên = Grace. Bạn sẽ thấy 3 bản ghi "Grace" (1 từ Leader, 2 từ 2 Follower), chứng tỏ dữ liệu đã được nhân bản.

Bấm nút "Sửa" (màu vàng) của bất kỳ bản ghi "Grace" nào. Nhập Sydney và nhấn OK.

Kết quả: "Nhật ký" sẽ hiển thị logic replicate_update được gửi đến cả 2 Follower.

Bấm nút "Xóa" (màu đỏ) của một bản ghi "Grace".

Kết quả: "Nhật ký" sẽ hiển thị logic replicate_delete và các bản ghi "Grace" khác cũng sẽ biến mất.

Kịch bản 3: Mô phỏng lỗi (Fault Tolerance)
Trên giao diện, trong mục "Trạng thái hệ thống", nhấn nút "Tắt 🛑" bên cạnh Follower 2 (5002).

Xác nhận hộp thoại.

Trang sẽ tải lại.

Kết quả: Follower 2 bây giờ sẽ hiển thị trạng thái "Offline" với chấm đỏ.

Bây giờ, Chèn một bản ghi mới (Tên = Test, Tuổi = 99, ...).

Kết quả: Quan sát "Nhật ký hoạt động". Bạn sẽ thấy hệ thống chỉ Gửi sao chép tới Follower 1 mà không gửi cho Follower 2 nữa.

Điều này chứng minh Leader đã nhận biết được lỗi và điều chỉnh hành vi sao chép, đảm bảo hệ thống không bị treo vì một nút đã chết.
