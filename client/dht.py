import time
import adafruit_dht 
import board 
from multiprocessing import Queue 
import RPi.GPIO as GPIO 

GPIO.setmode(GPIO.BCM)
# --- Cấu hình Relay ---
RELAY_GPIO_PIN = 14  
HUMIDITY_THRESHOLD_ON = 79.0  
HUMIDITY_THRESHOLD_OFF = 82.0 

relay_state = False 

def setup_relay():
    global relay_state 
    GPIO.setup(RELAY_GPIO_PIN, GPIO.OUT)
    GPIO.output(RELAY_GPIO_PIN, GPIO.HIGH) 
    relay_state = False 
    print(f"RELAY: Relay trên GPIO {RELAY_GPIO_PIN} đã được thiết lập, trạng thái ban đầu: TẮT (GPIO HIGH).")

def control_relay(current_humidity):
    global relay_state
    
    if current_humidity <= HUMIDITY_THRESHOLD_ON:
        if not relay_state: 
            GPIO.output(RELAY_GPIO_PIN, GPIO.LOW) 
            relay_state = True 
    
    elif current_humidity > HUMIDITY_THRESHOLD_OFF:
        if relay_state: 
            GPIO.output(RELAY_GPIO_PIN, GPIO.HIGH) 
            relay_state = False 
    

def run_dht_sensor(dht_queue: Queue):

    global relay_state 
    dht_device = None
    try:
        setup_relay() 
        dht_device = adafruit_dht.DHT22(board.D4) 
        print("DHT: Cảm biến DHT22 đã khởi tạo trên chân D4.")
        
        while True:
            temperature_c = None 
            humidity = None      
            try:
                temperature_c = dht_device.temperature
                humidity = dht_device.humidity
                # print(f"DHT Temp={temperature_c}°C, Humid={humidity}%")


                if temperature_c is not None and humidity is not None:
                    control_relay(humidity)

                    current_relay_status = 1 if relay_state else 0 
                    data_packet = {
                        "temperature": round(temperature_c, 1), 
                        "humidity": round(humidity, 1),
                        "relay_status": current_relay_status 
                    }
                    while not dht_queue.empty():
                        try:
                            dht_queue.get_nowait()
                        except Exception: 
                            break 
                    dht_queue.put(data_packet)
                    print(f"DHT Sent: Temp={data_packet['temperature']}°C, Humid={data_packet['humidity']}%, Relay={data_packet['relay_status']}")
                else:
                    print("DHT: Không đọc được giá trị hợp lệ từ cảm biến (một hoặc cả hai là None).")
                    pass 

            except RuntimeError as error:
                print(f"DHT: Lỗi đọc cảm biến (RuntimeError): {error}")
                pass 
            except Exception as e:
                print(f"DHT: Lỗi không xác định trong vòng lặp đọc DHT: {e}")
            
            time.sleep(30) 

    except KeyboardInterrupt:
        print("DHT: Dừng chương trình đọc DHT.")
    except Exception as e:
        print(f"DHT: Lỗi nghiêm trọng trong tiến trình DHT: {e}")
    finally:
        if dht_device:
            print("DHT: Giải phóng tài nguyên cảm biến DHT.")
            dht_device.exit()
        print("RELAY: Dọn dẹp GPIO cho relay.")
        GPIO.cleanup(RELAY_GPIO_PIN) 

if __name__ == '__main__':
    test_dht_queue = Queue()
    try:
        run_dht_sensor(test_dht_queue)
    except KeyboardInterrupt:
        print("Test DHT dừng.")
    finally:
        while not test_dht_queue.empty():
            retrieved_data = test_dht_queue.get_nowait()
            print(f"Dữ liệu còn lại trong queue test: {retrieved_data}")
        print("RELAY (Test): Kết thúc test, GPIO đã được xử lý trong run_dht_sensor.")
