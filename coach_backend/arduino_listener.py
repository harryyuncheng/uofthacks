import serial
import time
import serial.tools.list_ports
from coach_manager import get_or_create_user_by_nfc, set_coach_type

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
                # Read line from serial
                line = ser.readline().decode('utf-8').strip()
                
                # Basic validation that it looks like a hex UID (e.g., "0415A2C3")
                if line and len(line) >= 8: 
                    print(f"Tag Detected: {line}")
                    
                    # Initialize or fetch the user via Totem link
                    user = get_or_create_user_by_nfc(line)
                    
                    # Log essential info
                    print(f"Active User: {user.get('name')}")
                    print(f"User ID: {user.get('user_id')}")
                    print(f"Type: {user.get('coach_type', 'unset')}")
                    
                    if not user.get('onboarding_completed'):
                        print("ACTION REQUIRED: Ask user if they want 'personal' or 'corporate' coaching.")
                        # Simulating setting it for demo purposes if you want, or wait for voice/UI command
                    else:
                        print(f"System: {user.get('system_instruction')}")
                        
        except KeyboardInterrupt:
            print("\nStopping NFC Listener...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)
                    
        except KeyboardInterrupt:
            print("\nStopping NFC Listener...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    # You can list available ports with: python -m serial.tools.list_ports
    listen_for_nfc()
