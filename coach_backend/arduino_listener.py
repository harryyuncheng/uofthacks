import sys 
import json
import serial
import time
import serial.tools.list_ports
from session_loader import load_session

# Configuration
BAUD_RATE = 115200

def find_arduino_port():
    """
    Scans available ports and tries to identify the Arduino.
    Prioritizes 'usbmodem' or 'usbserial' ports on Mac.
    """
    ports = list(serial.tools.list_ports.comports())
    
    # Priority list of keywords to look for
    keywords = ["usbmodem", "usbserial", "Arduino", "CH340"]
    
    for p in ports:
        # Check description and device path
        full_info = f"{p.device} {p.description} {p.manufacturer}".lower()
        
        for k in keywords:
            if k.lower() in full_info:
                print(f"Found candidate port: {p.device}")
                return p.device
                
    # Fallback to the first available port if nothing matches
    if ports:
        print(f"No specific Arduino found, trying first port: {ports[0].device}")
        return ports[0].device
        
    return None

def listen_for_nfc():
    serial_port = find_arduino_port()
    
    if not serial_port:
        print("Error: No serial ports found. Is the Arduino connected?")
        return

    try:
        ser = serial.Serial(serial_port, BAUD_RATE, timeout=1)
        print(f"Listening for NFC tags on {serial_port}...")
    except serial.SerialException as e:
        print(f"Error opening serial port {serial_port}: {e}")
        return

    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if line.startswith("NFC_ID:"):
                    raw_nfc = line.split(":")[1].strip()
                    
                    # Instead of just printing text, we load the full session
                    # and output JSON for Electron to consume
                    session_data = load_session(raw_nfc)
                    
                    # FLUSH is critical for Electron to see it immediately
                    print(json.dumps(session_data))
                    sys.stdout.flush() 
                    
        except KeyboardInterrupt:
            break
        except Exception as e:
            # Send error as JSON too so frontend knows
            error_msg = {"type": "error", "message": str(e)}
            print(json.dumps(error_msg))
            sys.stdout.flush()
            time.sleep(1)

if __name__ == "__main__":
    # You can list available ports with: python -m serial.tools.list_ports
    listen_for_nfc()
