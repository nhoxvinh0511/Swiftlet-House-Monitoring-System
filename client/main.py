from multiprocessing import Process, Queue
import time

# Import hàm từ module

def run_bird_counter_process(queue): 
    import bird_counter 
    bird_counter.run_counter(queue)

def run_dht_sensor_process(dht_queue): 
    import dht 
    dht.run_dht_sensor(dht_queue)

def run_send_to_server_process(bird_queue, dht_queue): 
    import send_to_server 
    send_to_server.send_data(bird_queue, dht_queue)

if __name__ == "__main__":
    bird_data_queue = Queue()  
    dht_data_queue = Queue()   

    #Khởi tạo các tiến trình
    print("MAIN: Khởi tạo các tiến trình...")
    counter_process = Process(target=run_bird_counter_process, args=(bird_data_queue,))
    dht_process = Process(target=run_dht_sensor_process, args=(dht_data_queue,))
    sender_process = Process(target=run_send_to_server_process, args=(bird_data_queue, dht_data_queue,))

    # Bắt đầu các tiến trình
    print("MAIN: Bắt đầu các tiến trình...")
    counter_process.start()
    dht_process.start()
    sender_process.start()

    print("MAIN: Đã khởi động cả ba tiến trình.")
    print("MAIN: Nhấn Ctrl+C để dừng.")

    try:
        while True:
            time.sleep(1)
            # Kiểm tra xem các tiến trình còn sống
            if not counter_process.is_alive():
                print("MAIN: Tiến trình đếm chim đã dừng.")
                break
            if not dht_process.is_alive():
                print("MAIN: Tiến trình DHT đã dừng.")
                break
            if not sender_process.is_alive():
                print("MAIN: Tiến trình gửi dữ liệu đã dừng.")
                break
                
    except KeyboardInterrupt:
        print("\nMAIN: Nhận tín hiệu KeyboardInterrupt. Đang dừng các tiến trình...")
    finally:
        print("MAIN: Dừng tiến trình đếm chim...")
        if counter_process.is_alive():
            counter_process.terminate() 
            counter_process.join(timeout=5)
            if counter_process.is_alive():
                 print("MAIN: Tiến trình đếm chim không dừng, buộc dừng (kill)...")
                 counter_process.kill() 

        print("MAIN: Dừng tiến trình DHT...")
        if dht_process.is_alive():
            dht_process.terminate()
            dht_process.join(timeout=5)
            if dht_process.is_alive():
                 print("MAIN: Tiến trình DHT không dừng, buộc dừng (kill)...")
                 dht_process.kill()

        print("MAIN: Dừng tiến trình gửi dữ liệu...")
        if sender_process.is_alive():
            sender_process.terminate()
            sender_process.join(timeout=5)
            if sender_process.is_alive():
                 print("MAIN: Tiến trình gửi dữ liệu không dừng, buộc dừng (kill)...")
                 sender_process.kill()
        
        print("MAIN: Tất cả các tiến trình đã được yêu cầu dừng. Chương trình kết thúc.")
