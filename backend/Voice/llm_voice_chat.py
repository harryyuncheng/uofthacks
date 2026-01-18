import os
import queue
import time
import threading
import azure.cognitiveservices.speech as speechsdk
from openai import OpenAI
from dotenv import load_dotenv
from elevenlabs import stream
from elevenlabs.client import ElevenLabs

# Load environment variables
load_dotenv()

# Configuration
# Ensure you have these in your .env file:
# SPEECH_KEY, SPEECH_REGION, OPENROUTER_API_KEY, ELEVENLABS_API_KEY
SPEECH_KEY = os.getenv('SPEECH_KEY')
SPEECH_REGION = os.getenv('SPEECH_REGION')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
OPENROUTER_MODEL = "google/gemini-2.5-flash-preview-09-2025"

# Initialize ElevenLabs client
elevenlabs_client = None
if ELEVENLABS_API_KEY:
    elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
else:
    print("Warning: ELEVENLABS_API_KEY not found. Voice output disabled.")

# Shared queue for transcribed text
transcription_queue = queue.Queue()

def setup_speech_recognition():
    if not SPEECH_KEY or not SPEECH_REGION:
        raise ValueError("Please set SPEECH_KEY and SPEECH_REGION in your .env file.")

    speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SPEECH_REGION)
    speech_config.speech_recognition_language="en-US"
    
    # Optional: Filter out profanity if desired
    speech_config.set_profanity(speechsdk.ProfanityOption.Raw)

    audio_config = speechsdk.audio.AudioConfig(use_default_microphone=True)
    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)
    
    # Callback for when a complete utterance is recognized
    def recognized_cb(evt):
        text = evt.result.text
        if text:
            print(f"USER (Voice): {text}")
            transcription_queue.put(text)

    # Connect the callback
    speech_recognizer.recognized.connect(recognized_cb)
    
    return speech_recognizer

def get_complete_utterance(timeout=1):
    """
    Waits for text from the transcription queue. 
    Accumulates segments until silence (timeout) is detected.
    """
    accumulated_text = []
    
    # Wait for the first segment (blocking)
    # This call blocks until the user starts speaking
    first_segment = transcription_queue.get()
    accumulated_text.append(first_segment)
    
    # Collect subsequent segments until timeout (user pauses)
    while True:
        try:
            segment = transcription_queue.get(timeout=timeout)
            accumulated_text.append(segment)
        except queue.Empty:
            break
            
    return " ".join(accumulated_text)

def process_conversations(speech_recognizer):
    if not OPENROUTER_API_KEY:
        print("Warning: OPENROUTER_API_KEY not found. LLM features disabled.")
        return

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    
    conversation_history = [
        {"role": "system", "content": "You are a helpful voice assistant. Keep your responses concise and conversational."}
    ]

    print("Ready to chat! Speak into your microphone.")
    
    while True:
        try:
            # 1. Speech to Text: Wait for full utterance
            full_query = get_complete_utterance()
            print(f"\nProcessing full query: {full_query}")
            
            # Update history
            conversation_history.append({"role": "user", "content": full_query})
            
            # Stop recognition to prevent self-hearing
            if speech_recognizer:
                try:
                    speech_recognizer.stop_continuous_recognition_async().get()
                except Exception:
                    pass

            # 2. Text to LLM to Text + Audio Stream
            # We use a generator to stream text to ElevenLabs while collecting it for history
            full_response_container = []

            def response_generator():
                print("Assistant is thinking...")
                try:
                    llm_stream = client.chat.completions.create(
                        model=OPENROUTER_MODEL,
                        messages=conversation_history,
                        stream=True
                    )
                    
                    print("AI: ", end="", flush=True)
                    for chunk in llm_stream:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            print(content, end="", flush=True)
                            full_response_container.append(content)
                            yield content
                    print() # Newline after response
                except Exception as e:
                    print(f"Error communicating with LLM: {e}")

            if elevenlabs_client:
                try:
                    # Collect chunks and process sentences for immediate playback
                    current_buffer = ""
                    for chunk in response_generator():
                        current_buffer += chunk
                        # Heuristic: split on punctuation that suggests end of sentence
                        if len(current_buffer) > 4 and any(current_buffer.endswith(end) for end in [". ", "? ", "! ", ".\n", "?\n", "!\n", ".", "?", "!"]):
                            audio_stream = elevenlabs_client.text_to_speech.convert(
                                text=current_buffer,
                                voice_id="ljX1ZrXuDIIRVcmiVSyR", 
                                model_id="eleven_turbo_v2_5"
                            )
                            stream(audio_stream)
                            current_buffer = ""
                    
                    # Play any remaining text
                    if current_buffer.strip():
                        audio_stream = elevenlabs_client.text_to_speech.convert(
                            text=current_buffer,
                            voice_id="ljX1ZrXuDIIRVcmiVSyR",
                            model_id="eleven_turbo_v2_5"
                        )
                        stream(audio_stream)
                except Exception as e:
                    print(f"\nError with ElevenLabs stream: {e}")

            else:
                # Fallback if no ElevenLabs key: just run the generator
                for _ in response_generator(): pass
            
            # Resume recognition
            if speech_recognizer:
                try:
                    # Clear any potential buffered audio/transcription from the queue
                    with transcription_queue.mutex:
                        transcription_queue.queue.clear()
                    speech_recognizer.start_continuous_recognition_async().get()
                except Exception:
                    pass
            
            # Reconstruct full response
            response_text = "".join(full_response_container)
            
            if response_text:
                # Update history with AI response
                conversation_history.append({"role": "assistant", "content": response_text})
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error in conversation loop: {e}")

def main():
    try:
        recognizer = setup_speech_recognition()
        
        # Start recognition in background
        recognizer.start_continuous_recognition()
        
        # Run the conversation loop in the main thread
        process_conversations(recognizer)
        
    except KeyboardInterrupt:
        print("\nStopping...")
        if 'recognizer' in locals():
            recognizer.stop_continuous_recognition()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
