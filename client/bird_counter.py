import pigpio
import time
from collections import deque
from multiprocessing import Queue
from datetime import date

# --- Cấu hình cảm biến ---
TRIG_PINS = [2, 17, 22, 24, 5, 16]
ECHO_PINS = [3, 27, 23, 25, 6, 26]

NUM_SENSORS = 6
MIN_DISTANCE = 2
MAX_DISTANCE = 89
MAX_INTERVAL = 0.34
COOLDOWN = 0.045

MORNING_START     = 4    # 4h–10h chim thường bay ra
MORNING_END       = 10
EVENING_START     = 15   # 15h–20h chim thường bay vào
EVENING_END       = 20
NEAR_SIMULTANEOUS = 0.2 # t <= 24ms

event_queue = deque(maxlen=100)
last_active = [0] * NUM_SENSORS
chimTong = 9
chimVao  = 10
chimRa   = 367

# biến lưu ngày lần cuối đã reset
_last_reset_date = date.today()

# Khởi tạo pigpio
pi = pigpio.pi()
if not pi.connected:
    raise RuntimeError("Không thể kết nối với pigpiod!")

# Cấu hình các chân TRIG và ECHO
for i in range(NUM_SENSORS):
    pi.set_mode(TRIG_PINS[i], pigpio.OUTPUT)
    pi.set_mode(ECHO_PINS[i], pigpio.INPUT)
    pi.write(TRIG_PINS[i], 0)

time.sleep(1) 

# Đọc khoảng cách
def read_distance(trig, echo):
    # Phát tín hiệu TRIG
    pi.write(trig, 1)
    time.sleep(0.00001) 
    pi.write(trig, 0)

    # Đợi tín hiệu ECHO
    start_tick = pi.get_current_tick()
    pulse_start = pulse_end = None

    while pi.read(echo) == 0:
        pulse_start = pi.get_current_tick()
        if (pi.get_current_tick() - start_tick) > 20000:  
            return 999

    while pi.read(echo) == 1:
        pulse_end = pi.get_current_tick()
        if (pi.get_current_tick() - start_tick) > 20000:  
            return 999

    if pulse_start is None or pulse_end is None:
        return 999

    # Tính toán khoảng cách
    duration = (pulse_end - pulse_start) / 1e6  
    distance = (duration * 34300) / 2 
    return distance if 0 < distance < 130 else 999

def enqueue(sensor_id, timestamp):
    event_queue.append((sensor_id, timestamp))

def check_events(phase):
    global chimTong, chimVao, chimRa
    events = list(event_queue)

    i = 0
    while i < len(events):
        id1, t1 = events[i]
        j = i + 1
        while j < len(events):
            id2, t2 = events[j]

            # chỉ xét cùng cặp hoặc nhóm kề nhau 
            grp1, grp2 = id1//2, id2//2
            if id1 == id2 or abs(grp1 - grp2) > 1:
                j += 1
                continue

            if abs(t1 - t2) <= MAX_INTERVAL:
                even_time, odd_time = (t1, t2) if id1%2==0 else (t2, t1)
                diff = abs(even_time - odd_time)
                action_taken = False

                # Gần như đồng thời -> dùng phase
                if diff <= NEAR_SIMULTANEOUS:
                    if phase == 'morning':
                        # chim ra
                        chimTong = max(0, chimTong-1)
                        chimRa += 1
                        action_taken = True
                    elif phase == 'evening':
                        # chim vào
                        chimTong += 1
                        chimVao += 1
                        action_taken = True
                # không gần -> logic gốc
                else:
                    if even_time < odd_time:
                        chimTong += 1
                        chimVao += 1
                        action_taken = True
                    elif odd_time < even_time:
                        chimTong = max(0, chimTong-1)
                        chimRa += 1
                        action_taken = True

                if action_taken:
                    # xóa sự kiện đã xử lý
                    try:
                        event_queue.remove((id1, t1))
                        event_queue.remove((id2, t2))
                    except ValueError:
                        pass
                    return

            j += 1
        i += 1


def get_chim_tong():
    return chimTong

def get_time_phase():
    h = time.localtime().tm_hour
    if MORNING_START <= h < MORNING_END:
        return 'morning'
    elif EVENING_START <= h < EVENING_END:
        return 'evening'
    return None

def run_counter(queue):
    global chimTong, chimVao, chimRa, _last_reset_date
    try:
        while True:
            today = date.today()
            if today != _last_reset_date:
                # lưu lại giá trị cũ
                daily_vao   = chimVao
                daily_ra    = chimRa
                daily_tong  = chimTong
                # gửi gói 
                if queue:
                    queue.put({
                        "chimVao":       chimVao,
                        "chimRa":        chimRa,
                        "chimTong":      chimTong,
                        "chimVaoDaily":  daily_vao,
                        "chimRaDaily":   daily_ra,
                        "chimTongDaily": daily_tong,
                        "timestamp":     _last_reset_date.isoformat(),
                        "daily_report":  True
                    })
                # reset cho ngày mới 
                chimVao = 0
                chimRa  = 0
                _last_reset_date = today

            phase = get_time_phase()     
            now   = time.time()

            if phase == 'morning':
                sensor_ids = range(NUM_SENSORS-1, -1, -1)
            else:
                sensor_ids = range(NUM_SENSORS)

            for i in sensor_ids:
                if time.time() - last_active[i] < COOLDOWN:
                    continue
                dist = read_distance(TRIG_PINS[i], ECHO_PINS[i])
                if MIN_DISTANCE < dist < MAX_DISTANCE:
                    enqueue(i, time.time())
                    last_active[i] = time.time()
                if i != sensor_ids[-1]:
                    time.sleep(0.0065)

            check_events(phase)
            # Gửi thường xuyên ba biến chính
            if queue:
                queue.put({
                    "chimVao":  chimVao,
                    "chimRa":   chimRa,
                    "chimTong": chimTong
                })
            time.sleep(0.0065)
    finally:
        pi.stop()

if __name__ == "__main__":
    queue = Queue()
    run_counter(queue)