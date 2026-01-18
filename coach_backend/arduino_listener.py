import serial
import time
from coach_manager import get_or_create_coach

# Configure your serial port here. 
# On Mac it's often /dev/tty.usbmodem... or /dev/tty.usbserial...
# On Windows it's COM3, COM4, etc.
SERIAL_PORT = "/dev/tty.usbmodem13101" 
BAUD_RATE = 115200

def listen_for_nfc():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Listening for NFC tags on {SERIAL_PORT}...")
    except serial.SerialException as e:
        print(f"Error opening serial port {SERIAL_PORT}: {e}")
        return

    while True:
        try:
            if ser.in_waiting > 0:
                # Read line from serial
                line = ser.readline().decode('utf-8').strip()
                
                # Basic validation that it looks like a hex UID (e.g., "0415A2C3")
                if line and len(line) >= 8: 
                    print(f"Tag Detected: {line}")
                    
                    # Initialize or fetch the coach
                    coach = get_or_create_coach(line)
                    
                    # Log essential info
                    print(f"Active Coach ID: {coach.get('nfc_id')}")
                    print(f"Type: {coach.get('coach_type', 'unset')}")
                    
                    if not coach.get('onboarding_completed'):
                        print("ACTION REQUIRED: Ask user if they want 'personal' or 'corporate' coaching.")
                    else:
                        print(f"System: {coach.get('system_instruction')}")
                    
        except KeyboardInterrupt:
            print("\nStopping NFC Listener...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    # You can list available ports with: python -m serial.tools.list_ports
    listen_for_nfc()
