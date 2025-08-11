import requests
import time
from datetime import datetime, timezone, timedelta

# Cấu hình
SERVER_URL = "http://100.111.53.26:5000/api/update" 
GMT7 = timezone(timedelta(hours=7)) 

# Hàm chính gửi dữ liệu lên server 
def send_data(bird_queue, dht_queue):
    """
    Hàm này liên tục chạy để lấy dữ liệu từ các hàng đợi (queue)
    và gửi chúng lên server định kỳ.
    Nó xử lý cả dữ liệu "trực tiếp" (live) và dữ liệu "báo cáo hàng ngày" (daily report).
    """

    # Biến lưu trữ dữ liệu trực tiếp 
    live_chim_vao = 0
    live_chim_ra = 0
    live_chim_tong = 0 
    live_temperature = None
    live_humidity = None
    live_relay_status = 0
    
    pending_daily_vao = None
    pending_daily_ra = None
    pending_daily_tong = None 
    pending_daily_report_date = None 

    try:
        while True:
            if bird_queue is not None:
                while not bird_queue.empty(): 
                    try:
                        packet = bird_queue.get_nowait() 
                        if isinstance(packet, dict):
                            if packet.get("daily_report") is True:
                                pending_daily_vao = packet.get("chimVaoDaily")
                                pending_daily_ra = packet.get("chimRaDaily")
                                pending_daily_tong = packet.get("chimTongDaily")
                                pending_daily_report_date = packet.get("timestamp")

                                live_chim_vao = packet.get("chimVao", live_chim_vao)
                                live_chim_ra = packet.get("chimRa", live_chim_ra)
                                live_chim_tong = packet.get("chimTong", live_chim_tong)
                            else:
                                live_chim_vao = packet.get("chimVao", live_chim_vao)
                                live_chim_ra = packet.get("chimRa", live_chim_ra)
                                live_chim_tong = packet.get("chimTong", live_chim_tong)
                    except Exception: 
                        break

            if dht_queue is not None:
                while not dht_queue.empty(): 
                    try:
                        dht_data = dht_queue.get_nowait()
                        if isinstance(dht_data, dict):
                            live_temperature = dht_data.get("temperature", live_temperature)
                            live_humidity = dht_data.get("humidity", live_humidity)
                            live_relay_status = dht_data.get("relay_status", live_relay_status)
                    except Exception: 
                        break

            payload = {
                "chimVao": live_chim_vao,
                "chimRa": live_chim_ra,
                "chimTong": live_chim_tong,
                "temperature": live_temperature,
                "humidity": live_humidity,
                "relay_status": live_relay_status,
            }

            if pending_daily_report_date is not None:
                payload["timestamp"] = pending_daily_report_date
                payload["daily_report"] = True 
                payload["chimVaoDaily"] = pending_daily_vao
                payload["chimRaDaily"] = pending_daily_ra
                payload["chimTongDaily"] = pending_daily_tong

                pending_daily_vao = None
                pending_daily_ra = None
                pending_daily_tong = None
                pending_daily_report_date = None
            else:
                now_utc = datetime.now(timezone.utc)
                now_gmt7 = now_utc.astimezone(GMT7)
                payload["timestamp"] = now_gmt7.isoformat() 

            try:
                response = requests.post(SERVER_URL, json=payload, timeout=10) 
                if response.status_code == 200:
                    # print(f"SENDER: Gửi thành công: {payload}") 
                    pass
                else:
                    print(f"SENDER: Lỗi phản hồi từ server: {response.status_code}, {response.text}")
            except requests.exceptions.RequestException as e: 
                print(f"SENDER: Không gửi được (lỗi request): {e}")
            except Exception as e: 
                print(f"SENDER: Không gửi được (lỗi khác): {e}")
            time.sleep(10)

    except KeyboardInterrupt: 
        print("\nSENDER: Dừng gửi dữ liệu.")
    except Exception as e: 
        print(f"LỖI trong send_to_server: {e}")
