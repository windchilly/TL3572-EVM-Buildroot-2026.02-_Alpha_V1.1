#!/usr/bin/env python3

import os
import time
import threading

# GPIO pin configuration
power_ctrl_pin = 25
power_detect_pin = 26

def setup_gpio():
    """Setup GPIO pins"""
    # POWER_CTRL
    if not os.path.exists(f"/sys/class/gpio/gpio{power_ctrl_pin}"):
        with open("/sys/class/gpio/export", "w") as f:
            f.write(str(power_ctrl_pin))
    
    with open(f"/sys/class/gpio/gpio{power_ctrl_pin}/direction", "w") as f:
        f.write("out")
    
    with open(f"/sys/class/gpio/gpio{power_ctrl_pin}/value", "w") as f:
        f.write("1")

    # DECT
    if not os.path.exists(f"/sys/class/gpio/gpio{power_detect_pin}"):
        with open("/sys/class/gpio/export", "w") as f:
            f.write(str(power_detect_pin))
    
    with open(f"/sys/class/gpio/gpio{power_detect_pin}/direction", "w") as f:
        f.write("in")

def save_data(complete_event):
    """Save system data and signal when complete"""
    print("Saving system logs...")
    os.system("mkdir -p /usr/data")  # Save log info
    os.system("dmesg > /usr/data/log.txt")  # Save log info

    print("Sync system data...")
    os.system("sync")  # Sync data

    print("system log and data save already completed!")
    complete_event.set()  # Signal that save is complete

def countdown(complete_event):
    """Countdown before poweroff, waiting for save to complete"""
    for i in range(3, 0, -1):
        print(f"System will run poweroff in {i} seconds...")
        time.sleep(1)
    
    # Wait for save to complete if not already done
    if not complete_event.is_set():
        complete_event.wait()  # Block until save is complete
    
    # Now power off (save is guaranteed to be complete)
    print("Powering off system...\n\n\n")
    os.system("poweroff")  # Power off system

def monitor_power():
    """Monitor power status and perform actions when power is off"""
    while True:
        try:
            with open(f"/sys/class/gpio/gpio{power_detect_pin}/value", "r") as f:
                dect_value = int(f.read().strip())
            
            if dect_value == 0:
                print("\n\n\nPower is detected to be off and is currently powered by the TL-PLP module")

                """ Change the printing level to avoid excessive information """
                os.system("echo 1  4  1  7 > /proc/sys/kernel/printk")

                # Event to signal when data save is complete
                save_complete = threading.Event()

                # Start data save and countdown in parallel
                save_thread = threading.Thread(target=save_data, args=(save_complete,))
                countdown_thread = threading.Thread(target=countdown, args=(save_complete,))

                save_thread.start()
                countdown_thread.start()

                # Wait for both threads to complete
                save_thread.join()
                countdown_thread.join()

                break
        except Exception as e:
            print(f"Error reading GPIO: {e}")
        
        time.sleep(1)  # Check every second

if __name__ == "__main__":
    try:
        setup_gpio()
        monitor_power()

    except KeyboardInterrupt:
        print("\nScript interrupted by user")

    except Exception as e:
        print(f"Error: {e}")
