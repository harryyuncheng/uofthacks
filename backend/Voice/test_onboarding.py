import sys
import os
import time

# Add current directory to path so we can import llm_voice_chat if run from elsewhere
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from llm_voice_chat import run_introduction_session, setup_speech_recognition

def main():
    print("Starting ONBOARDING (Introduction) test...")
    print("The system should verify environment variables and start the intro sequence.")
    print("Press Ctrl+C to exit.")
    
    try:
        # Setup real speech recognition
        # Note: We pass the recognizer to the session, which manages starting/stopping
        # to avoid capturing the AI's own voice during the intro.
        recognizer = setup_speech_recognition()
        
        # Run the introduction session
        run_introduction_session(recognizer)
        
    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    except Exception as e:
        print(f"\nError during test: {e}")
    finally:
        # Ensure it's stopped at the end
        if 'recognizer' in locals():
            try:
                recognizer.stop_continuous_recognition()
            except:
                pass

if __name__ == "__main__":
    main()
