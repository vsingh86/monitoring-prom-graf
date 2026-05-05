import time
import multiprocessing

def cpu_burner():
    # Infinite loop to max out a CPU core
    while True:
        pass

def mem_burner(gb):
    print(f"Allocating ~{gb}GB of memory...")
    # 1 GB is 1024*1024*1024 bytes.
    # Create a list of large byte objects
    chunk = b'a' * 1024 * 1024 # 1MB
    data = []
    for _ in range(int(gb * 1024)):
        data.append(chunk)
    print("Memory allocated! Holding...")
    while True:
        time.sleep(1)

if __name__ == '__main__':
    print("--- 🔴 HOST STRESS TESTER (For Layer 2 Demo) ---")
    print("1. Spike CPU (Max out all cores)")
    print("2. Spike Memory (Allocate 2GB RAM)")
    print("3. Spike Both")
    
    choice = input("Select an option (1-3): ")
    
    processes = []
    try:
        if choice in ['1', '3']:
            cores = multiprocessing.cpu_count()
            print(f"Starting CPU stress on {cores} cores...")
            for _ in range(cores):
                p = multiprocessing.Process(target=cpu_burner)
                p.start()
                processes.append(p)
                
        if choice in ['2', '3']:
            # Adjust the GB value here if you want a bigger spike
            p = multiprocessing.Process(target=mem_burner, args=(2,))
            p.start()
            processes.append(p)
            
        print("\n🔥 STRESS TEST RUNNING 🔥")
        print("Check your Grafana Layer 1 Saturation & Layer 2 Host panels.")
        print("Press Ctrl+C to stop and release resources.")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping stress test...")
        for p in processes:
            p.terminate()
        print("Resources released.")
