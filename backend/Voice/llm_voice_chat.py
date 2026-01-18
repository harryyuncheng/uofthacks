import json
import os
import sys
import queue
import time
import threading
import sys
import argparse
import io
import uuid
import certifi
from datetime import datetime
from pymongo import MongoClient
import azure.cognitiveservices.speech as speechsdk
from openai import OpenAI
from dotenv import load_dotenv, find_dotenv
from elevenlabs import stream
from elevenlabs.client import ElevenLabs

# Use simpleaudio for playback as a fallback if mpv fails in 'stream'
import simpleaudio as sa
from pydub import AudioSegment

# Load environment variables (look in root/parent dirs)
load_dotenv()
if not os.getenv("ELEVENLABS_API_KEY"):
    load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

# Configuration
# Ensure you have these in your .env file:
# SPEECH_KEY, SPEECH_REGION, OPENROUTER_API_KEY, ELEVENLABS_API_KEY
SPEECH_KEY = os.getenv('SPEECH_KEY')
SPEECH_REGION = os.getenv('SPEECH_REGION')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
OPENROUTER_MODEL = "google/gemini-2.5-flash-preview-09-2025"
MONGO_URL = os.getenv("MONGO_URL")

# MongoDB Setup
mongo_client = None
goals_collection = None
if MONGO_URL:
    try:
        mongo_client = MongoClient(MONGO_URL, tlsCAFile=certifi.where())
        db = mongo_client.get_database("totem_coach_db")
        goals_collection = db.get_collection("goals")
        print("Connected to MongoDB for goals.", file=sys.stderr)
    except Exception as e:
        print(f"Warning: MongoDB connection failed: {e}", file=sys.stderr)

# Initialize ElevenLabs client
elevenlabs_client = None
if ELEVENLABS_API_KEY:
    elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
else:
    print("Warning: ELEVENLABS_API_KEY not found. Voice output disabled.")

# Shared queue for transcribed text
transcription_queue = queue.Queue()

def wait_for_wake_word(speech_recognizer):
    print("Listening for wake word 'Hey Amir'...", file=sys.stderr)
    while True:
        try:
            # Check queue non-blocking or with short timeout
            text = transcription_queue.get(timeout=0.1)
            # print(f"Heard: {text}", file=sys.stderr)
            if "amir" in text.lower(): # fuzzy match
                 print(json.dumps({"type": "voice", "status": "wake_word_detected"}), flush=True)
                 # Drain the queue so the onboarding doesn't process the wake word as input
                 with transcription_queue.mutex:
                     transcription_queue.queue.clear()
                 return
        except queue.Empty:
            continue

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

def run_introduction_session(speech_recognizer):
    print("Starting Introduction Session...")
    
    if not OPENROUTER_API_KEY:
        print("Warning: OPENROUTER_API_KEY not found. LLM features disabled.")
        return

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

    # Specific objectives for the intro session
    objectives = [
        "Introduce yourself as Curtis, a helpful friend whose goal is to help the user fulfill their own goals.",
        "Ask for the user's name to get to know them.",
        "Ask the user for a list of their primary goals and what they hope to achieve with your help.",
        "Smoothly ask if the user has any goals left. If not, then exit the introduction mode, and go to normal coaching mode. Ask the user which goal they'd like to explore first."
    ]

    # Base system prompt for the persona
    base_system_prompt = (
        "In this session, you are meeting the user for the first time. "
        "Keep the conversation flowing naturally. Be enthusiastic and supportive. "
        "You are Curtis. "
        "CRITICAL: Limit your responses to a maximum of 2 sentences at a time. Be concise."
    )

    conversation_history = [
        {"role": "system", "content": base_system_prompt}
    ]

    current_objective_index = 0
    force_loop_back = False

    while True:
        try:
            # Logic to handle looping back from Objective 3 to Objective 2 (shifted indices)
            # We determine the next objective to inject based on the index
            if current_objective_index >= len(objectives):
                print("Introduction objectives complete.")
                break
            
            current_objective_text = objectives[current_objective_index]
            
            # Append the current objective to the history as a system instruction
            # effectively "injecting" it for this turn
            conversation_history.append({
                "role": "system", 
                "content": f"Current Objective: {current_objective_text}"
            })
            
            # --- Generate AI Response ---
            full_response_container = []
            
            def response_generator():
                print("Assistant is thinking (Intro Mode)...")
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
                    print()
                except Exception as e:
                    print(f"Error communicating with LLM: {e}")

            # Text-to-Speech logic (same as main)
            if elevenlabs_client:
                try:
                    current_buffer = ""
                    for chunk in response_generator():
                        current_buffer += chunk
                        if len(current_buffer) > 4 and any(current_buffer.endswith(end) for end in [". ", "? ", "! ", ".\n", "?\n", "!\n", ".", "?", "!"]):
                            audio_stream = elevenlabs_client.text_to_speech.convert(
                                text=current_buffer,
                                voice_id="ljX1ZrXuDIIRVcmiVSyR", 
                                model_id="eleven_turbo_v2_5"
                            )
                            stream(audio_stream)
                            current_buffer = ""
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
                for _ in response_generator(): pass

            assistant_response_text = "".join(full_response_container)
            conversation_history.append({"role": "assistant", "content": assistant_response_text})

            # Check if we are done with all objectives before asking for user input?
            # actually we need user input to proceed.
            
            # Resume recognition
            if speech_recognizer:
                try:
                    with transcription_queue.mutex:
                        transcription_queue.queue.clear()
                    speech_recognizer.start_continuous_recognition_async().get()
                except Exception:
                    pass

            # --- Wait for User Input ---
            user_input = get_complete_utterance()
            print(f"\nUSER: {user_input}")
            conversation_history.append({"role": "user", "content": user_input})

            # Stop recognition
            if speech_recognizer:
                try:
                    speech_recognizer.stop_continuous_recognition_async().get()
                except Exception:
                    pass

            # --- Background Data Parsing & Flow Control ---
            # We need to know if we should loop back or proceed.
            # We launch a thread to parse data (name, goals), and also determine flow.
            
            def info_parser_worker(u_text, obj_idx, ai_text):
                # This function calls LLM to parse extracted info
                parser_prompt = f"""
                Analyze the user's input in the context of the conversation.
                Current Objective Index: {obj_idx}
                AI Question: {ai_text}
                User Input: {u_text}
                
                Task:
                1. Extract relevant information. Return "goals" as a list of strings if any new goals are mentioned.
                2. If Objective Index is 3 (checking for more goals), determine if the user has MORE goals or is DONE.
                
                Return JSON format:
                {{
                    "extracted_data": {{ "goals": ["goal1", "goal2"] }},
                    "flow_control": "CONTINUE" | "LOOP_BACK_TO_GOALS" | "DONE"
                }}
                """
                
                try:
                     parse_completion = client.chat.completions.create(
                        model="google/gemini-2.5-flash-preview-09-2025", # Use a fast model
                        messages=[{"role": "system", "content": "You are a data extraction backend."},
                                  {"role": "user", "content": parser_prompt}],
                        response_format={"type": "json_object"}
                    )
                     result = parse_completion.choices[0].message.content
                     
                     # Clean up potential markdown formatting
                     if result.strip().startswith("```json"):
                         result = result.strip().split("```json")[1]
                         if result.strip().endswith("```"):
                             result = result.strip()[:-3]
                     elif result.strip().startswith("```"):
                         result = result.strip().split("```")[1]
                         if result.strip().endswith("```"):
                             result = result.strip()[:-3]

                     parsed_json = json.loads(result)
                     print(f"Parsed JSON: {parsed_json}", file=sys.stderr)
                     
                     # Store extracted_data to MongoDB and emit event
                     extracted_data = parsed_json.get("extracted_data", {})
                     goals_data = extracted_data.get("goals", [])
                     if not isinstance(goals_data, list):
                         if isinstance(goals_data, str):
                            goals_data = [goals_data]
                         else:
                            goals_data = []

                     saved_goals = []
                     if goals_data:
                         for g_text in goals_data:
                             # Always add to UI list
                             saved_goals.append(g_text)
                             
                             # Try to save to DB in background
                             if goals_collection is not None:
                                 new_goal = {
                                     "goal_id": str(uuid.uuid4()),
                                     "user_id": "demo_user", # Placeholder
                                     "title": g_text,
                                     "description": "",
                                     "progress": 0,
                                     "status": "in-progress",
                                     "subgoals": [],
                                     "created_at": datetime.now()
                                 }
                                 try:
                                     goals_collection.insert_one(new_goal)
                                 except Exception as e:
                                     print(f"Error inserting goal: {e}", file=sys.stderr)
                        
                         # Emit event to Electron
                         if saved_goals:
                             print(json.dumps({
                                 "type": "voice", 
                                 "status": "goals_updated", 
                                 "goals": saved_goals
                             }), flush=True)

                     return parsed_json
                except Exception as e:
                    print(f"Parser error: {e}", file=sys.stderr)
                    return None

            # For the purpose of flow control, we might need to block or use a shared variable.
            # Since the user said "Objective 4 might loop back", we need the result of parsing to decide the next step.
            # The prompt says "background after each response... return data... eventually sent to mongodb".
            # It implies the *parsing* is background, but *flow* might need to be synchronous effectively.
            # However, to keep it 'background', we can assume the main thread proceeds unless interrupted.
            # BUT: If we proceed to the wrong objective, it's bad.
            # Let's run it synchronously for the decision logic, but "conceptually" it's a background data task.
            # For this implementation, I will run it and wait for the Loop decision, because the next prompt DEPENDS on it.
            
            # NOTE: "gradually work through each of the numbered objectives... appending the objective ... to the llm input"
            # This means the MAIN loop controls the objectives.
            
            parser_result = info_parser_worker(user_input, current_objective_index, assistant_response_text)
            
            # Decide next step logic
            if current_objective_index == 2:
                # We just asked for goals. Move to check if they have more
                current_objective_index += 1
            elif current_objective_index == 3:
                # We asked if they have more goals.
                # Check parser result
                flow = parser_result.get("flow_control", "DONE") if parser_result else "DONE"
                if flow == "LOOP_BACK_TO_GOALS" or "yes" in user_input.lower(): # Fallback heuristic
                    # Go back to asking for goals (Index 2)
                    current_objective_index = 2
                else:
                    # Done with intro
                    current_objective_index += 1
            else:
                # Normal progression
                current_objective_index += 1

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"Error in intro session: {e}")
            break
            
    print("Exiting Introduction Session.")

def process_conversations(speech_recognizer):
    if not OPENROUTER_API_KEY:
        print("Warning: OPENROUTER_API_KEY not found. LLM features disabled.")
        return

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )
    
    # Load system prompt from file
    try:
        with open("system_prompt.txt", "r") as f:
            system_prompt = f.read().strip()
    except FileNotFoundError:
        system_prompt = "You are a helpful voice assistant. Keep your responses concise and conversational."

    conversation_history = [
        {"role": "system", "content": system_prompt}
    ]

    print("Ready to chat! Speak into your microphone.")

    # Speak greeting if provided
    if greeting:
        print(f"AI (Greeting): {greeting}")
        if elevenlabs_client:
            try:
                # Use text_to_speech.convert which returns a generator of bytes
                audio_stream = elevenlabs_client.text_to_speech.convert(
                    text=greeting,
                    voice_id="ljX1ZrXuDIIRVcmiVSyR", 
                    model_id="eleven_turbo_v2_5"
                )
                # Consume generator (stream) into full bytes for simpleaudio playback
                play_audio_bytes(b"".join(audio_stream))
            except Exception as e:
                print(f"Greeting Audio Error: {e}")
        conversation_history.append({"role": "assistant", "content": greeting})
    
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
                            # Generate full audio bytes instead of stream object
                            audio_stream = elevenlabs_client.text_to_speech.convert(
                                text=current_buffer,
                                voice_id="ljX1ZrXuDIIRVcmiVSyR", 
                                model_id="eleven_turbo_v2_5"
                            )
                            # Consume generator
                            play_audio_bytes(b"".join(audio_stream))
                            current_buffer = ""
                    
                    # Play any remaining text
                    if current_buffer.strip():
                        audio_stream = elevenlabs_client.text_to_speech.convert(
                            text=current_buffer,
                            voice_id="ljX1ZrXuDIIRVcmiVSyR",
                            model_id="eleven_turbo_v2_5"
                        )
                        play_audio_bytes(b"".join(audio_stream))
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
    parser = argparse.ArgumentParser(description='LLM Voice Chat')
    parser.add_argument('--prompt', type=str, help='System prompt for the AI', default="You are a helpful voice assistant. Keep your responses concise and conversational.")
    parser.add_argument('--greeting', type=str, help='Initial greeting to speak', default=None)
    args = parser.parse_args()

    try:
        # Start speech recognition first (to warm up mic)
        speech_recognizer = setup_speech_recognition()
        speech_recognizer.start_continuous_recognition()
        
        # 1. Wait for wake word
        wait_for_wake_word(recognizer)

        # 2. Run the onboarding conversation
        run_introduction_session(recognizer)
        
        # Optionally fall through to normal conversation if needed
        process_conversations(recognizer)
        
    except KeyboardInterrupt:
        print("\nStopping...")
        if 'speech_recognizer' in locals():
            speech_recognizer.stop_continuous_recognition()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
