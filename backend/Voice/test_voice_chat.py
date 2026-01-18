import threading
import time
import sys
import os

# Add current directory to path so we can import llm_voice_chat if run from elsewhere
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from llm_voice_chat import process_conversations, setup_speech_recognition

def main():
    print("Starting FULL voice chat test (Microphone ENABLED)...")
    print("Speak into your microphone to chat.")
    print("Press Ctrl+C to exit.")
    
    try:
        # Setup real speech recognition
        recognizer = setup_speech_recognition()
        
        # Start listening
        recognizer.start_continuous_recognition()
        print(">>> Listening for voice input...")
        
        # Run the conversation loop (blocks until user exit)
        process_conversations(recognizer)
        
    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    except Exception as e:
        print(f"\nError during test: {e}")
    finally:
        if 'recognizer' in locals():
            print("Stopping recognition...")
            recognizer.stop_continuous_recognition()

if __name__ == "__main__":
    main()
