from flask import Flask, request, jsonify, render_template
from datetime import datetime, timedelta, timezone
import json
import os
import sqlite3
import random # Thêm import này nếu chưa có

app = Flask(__name__, static_folder='static')
DATABASE_FILE = 'sensor_data.db'
latest_data = {}  

# Thiết lập SQLite.
def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row 
    return conn

# Khởi tạo cơ sở dữ liệu và các bảng
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Bảng lưu trữ các bản ghi dữ liệu cảm biến theo thời gian.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL UNIQUE,
            chimVao INTEGER,
            chimRa INTEGER,
            chimTong INTEGER,
            temperature REAL,
            humidity REAL,
            relay_status INTEGER
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON readings (timestamp);")

    # Bảng lưu trữ báo cáo tổng kết số lượng chim hàng ngày.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_reports (
            date TEXT PRIMARY KEY,
            chimVaoDaily INTEGER,
            chimRaDaily INTEGER,
            chimTongDaily INTEGER
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_daily_reports_date ON daily_reports (date);")
    conn.commit()
    conn.close()
    print("SERVER: Cơ sở dữ liệu đã được khởi tạo (bảng readings và daily_reports).")

# Tải dữ liệu mới nhất từ cơ sở dữ liệu vào cache khi khởi động server.
def load_latest_data_from_db():
    global latest_data
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM readings ORDER BY timestamp DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            latest_data = dict(row)
            print("SERVER: Đã tải dữ liệu mới nhất từ DB vào cache.")
        else:
            latest_data = {
                "humidity": None, "temperature": None, "relay_status": None,
                "timestamp": None, "chimVao": None, "chimRa": None, "chimTong": None
            }
            print("SERVER: DB trống, cache latest_data được khởi tạo với giá trị None.")
    except sqlite3.Error as e:
        print(f"SERVER: Lỗi tải dữ liệu mới nhất từ DB: {e}")
        latest_data = { 
            "humidity": None, "temperature": None, "relay_status": None,
            "timestamp": None, "chimVao": None, "chimRa": None, "chimTong": None
        }

# Xóa dữ liệu cũ.
def delete_old_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        cursor.execute("DELETE FROM readings WHERE timestamp < ?", (thirty_days_ago,))
        deleted_readings = cursor.rowcount
        if deleted_readings > 0:
            print(f"SERVER: Đã xóa {deleted_readings} bản ghi cũ từ bảng 'readings'.")

        one_year_ago = (datetime.now(timezone.utc) - timedelta(days=365)).strftime('%Y-%m-%d')
        cursor.execute("DELETE FROM daily_reports WHERE date < ?", (one_year_ago,))
        deleted_daily_reports = cursor.rowcount
        if deleted_daily_reports > 0:
            print(f"SERVER: Đã xóa {deleted_daily_reports} bản ghi cũ từ bảng 'daily_reports'.")
            
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"SERVER: Lỗi xóa dữ liệu cũ: {e}")
        
# Route chính
@app.route('/')
def index():
    return render_template('dashboard.html')

# Route API
@app.route('/api/update', methods=['POST'])
def update_sensor_data():
    global latest_data
    data = request.get_json()
    
    if not data:
        return jsonify({"error": "Dữ liệu không hợp lệ: Không có dữ liệu"}), 400
    
    if "timestamp" not in data:
        return jsonify({"error": "Dữ liệu không hợp lệ: Thiếu timestamp"}), 400

    latest_data.update(data) 

    # Lưu vào cơ sở dữ liệu readings (giá trị hiện tại/liên tục)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO readings (timestamp, chimVao, chimRa, chimTong, temperature, humidity, relay_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(timestamp) DO UPDATE SET
                chimVao=excluded.chimVao,
                chimRa=excluded.chimRa,
                chimTong=excluded.chimTong,
                temperature=excluded.temperature,
                humidity=excluded.humidity,
                relay_status=excluded.relay_status
        ''', (data['timestamp'], data.get('chimVao'), data.get('chimRa'), data.get('chimTong'), 
              data.get('temperature'), data.get('humidity'), data.get('relay_status')))
        
        # lưu vào bảng daily_reports
        if data.get("daily_report") is True:
            report_date_str = data.get("timestamp") 
            report_date = report_date_str.split('T')[0] 

            chim_vao_daily = data.get("chimVaoDaily")
            chim_ra_daily = data.get("chimRaDaily")
            chim_tong_daily = data.get("chimTongDaily")

            if chim_vao_daily is not None and chim_ra_daily is not None and chim_tong_daily is not None:
                cursor.execute('''
                    INSERT INTO daily_reports (date, chimVaoDaily, chimRaDaily, chimTongDaily)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(date) DO UPDATE SET
                        chimVaoDaily=excluded.chimVaoDaily,
                        chimRaDaily=excluded.chimRaDaily,
                        chimTongDaily=excluded.chimTongDaily
                ''', (report_date, chim_vao_daily, chim_ra_daily, chim_tong_daily))
                print(f"SERVER: Đã lưu/cập nhật báo cáo hàng ngày cho {report_date}")
            else:
                print(f"SERVER: Nhận cờ daily_report nhưng thiếu dữ liệu đếm hàng ngày cho {report_date}.")

        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"SERVER: Lỗi lưu dữ liệu vào DB: {e}")
    
    if random.randint(1, 100) == 1: 
        delete_old_data()

    return jsonify({"status": "ok"}), 200

# Route API cung cấp dữ liệu mới nhất cho dashboard
@app.route('/api/data', methods=['GET'])
def get_sensor_data():
    return jsonify(latest_data)

# Route API cung cấp dữ liệu lịch sử cho các biểu đồ
@app.route('/api/historical_data', methods=['GET'])
def get_historical_data():
    range_type = request.args.get('range', 'day') 
    now = datetime.now(timezone.utc)
    start_time_dt = None

    if range_type == 'day':
        start_time_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_type == 'week':
        start_time_dt = now - timedelta(days=now.weekday()) 
        start_time_dt = start_time_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_type == 'month':
        start_time_dt = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return jsonify({"error": "Loại phạm vi không hợp lệ"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM readings WHERE timestamp >= ? ORDER BY timestamp ASC",
            (start_time_dt.isoformat(),)
        )
        rows = cursor.fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except sqlite3.Error as e:
        print(f"SERVER: Lỗi truy xuất dữ liệu lịch sử: {e}")
        return jsonify({"error": "Không thể truy xuất dữ liệu lịch sử"}), 500

# Route API cung cấp lịch sử báo cáo hàng ngày
@app.route('/api/daily_reports_history', methods=['GET'])
def get_daily_reports_history():
    days_to_fetch = int(request.args.get('days', 30)) # Mặc định lấy 30 ngày
    end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    start_date_dt = datetime.now(timezone.utc) - timedelta(days=days_to_fetch -1)
    start_date = start_date_dt.strftime('%Y-%m-%d')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM daily_reports WHERE date BETWEEN ? AND ? ORDER BY date ASC",
            (start_date, end_date)
        )
        rows = cursor.fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])
    except sqlite3.Error as e:
        print(f"SERVER: Lỗi truy xuất lịch sử báo cáo hàng ngày: {e}")
        return jsonify({"error": "Không thể truy xuất lịch sử báo cáo hàng ngày"}), 500

def load_config():
    return {"example_config_key": "example_value"}

# Route API lấy cấu hình
@app.route('/api/config', methods=['GET'])
def get_current_config():
    return jsonify(load_config())

# Route phục vụ trang dashboard chính
@app.route('/dashboard')
def dashboard_route():
    return render_template('dashboard.html')


if __name__ == '__main__':
    init_db()
    load_latest_data_from_db()
    # delete_old_data() 
    app.run(host='0.0.0.0', port=5000, debug=True)