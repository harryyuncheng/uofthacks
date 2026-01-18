# Totem Project - Next Steps & Implementation Plan

This document outlines the remaining tasks to fully integrate the NFC Coach functionality with the Frontend, Voice services (ElevenLabs), and Intelligence layer (Blackboard IO).

## 🟢 Phase 1: Deep Integration (Electron <-> Python)
Currently, `main.ts` spawns the python process, but we need robust bi-directional communication to trigger UI states.

- [ ] **Establish IPC Channels**:
    - Modify `arduino_listener.py` to print JSON-formatted logs that `main.ts` can parse easily.
    - Example output: `{"type": "coach_active", "data": {...}}`
    - In `main.ts`, parse these lines and send `ipcRenderer.send('coach-update', ...)` to the React frontend.
- [ ] **Frontend State Management**:
    - Create a React Context (`CoachContext`) to store:
        - `isCoachActive` (bool)
        - `coachProfile` (name, personality, type)
        - `interactionState` (listening, thinking, speaking)
- [ ] **Onboarding UI**:
    - If `coach_type` is `unset`, show a specific UI Prompt: "Personal or Corporate?".
    - Send the selection back to Python via Electron -> `stdin` of the Python process (or a separate API endpoint).

## 🗣️ Phase 2: Variable Voice (ElevenLabs & STT)
We need the Totem to speak and listen.

- [ ] **Speech-to-Text (STT)**:
    - Implement a "wake word" or "push-to-talk" loop in a new Python thread (or use the existing gesture "Quiet" gesture to toggle listening).
    - Use `speech_recognition` or OpenAI Whisper locally to convert user audio to text.
- [ ] **LLM Integration**:
    - Feed the STT text + Coach System Prompt + Blackboard IO Context into an LLM (OpenAI/Anthropic).
- [ ] **Text-to-Speech (TTS) with ElevenLabs**:
    - Sign up for ElevenLabs API.
    - Create a `VoiceManager` class in Python.
    - **Dynamic Voice Switching**:
        - If `coach_type == 'corporate'`, use a deeper, authoritative Voice ID.
        - If `coach_type == 'personal'`, use a warmer, energetic Voice ID.
    - Stream audio output directly from Python or send the audio buffer to Electron to play.

## 🧠 Phase 3: The Brain (RAG with Blackboard IO)
Blackboard IO will serve as the long-term memory vector store, allowing the coach to remember facts about the user.

- [ ] **Setup Blackboard IO**:
    - Initialize the Blackboard client in `rag_agent/`.
    - Create a "Collection" for each `nfc_id` (or filter by metadata).
- [ ] **Context Ingestion (Writing Memory)**:
    - When the user tells the coach a fact (e.g., "I'm training for a marathon"), extract this fact.
    - Send it to Blackboard IO: `client.add_documents(text="User is training for marathon", metadata={"nfc_id": "..."})`.
    - Update the local MongoDB `learned_context` string as a fallback.
- [ ] **Context Retrieval (Reading Memory)**:
    - Before sending a user query to the LLM, query Blackboard IO.
    - `relevant_facts = client.search(query=user_prompt, limit=3)`
    - Append these facts to the System Prompt:
        > "Context: You know the following about the user: [User is training for a marathon...]"

## 📋 Phase 4: Goal Tracking
- [ ] **Database Expansion**:
    - Flesh out the `Goal` model in `models.py`.
    - Add functions to `mark_goal_complete(goal_id)`.
- [ ] **Visual Dashboard**:
    - In React, when a Coach is active, show their tracked goals as floating widgets (using the existing Widget system).

## 🚀 Execution Order
1.  **Fix the Comms**: Get `arduino_listener.py` talking to React via `main.ts` JSON parsing.
2.  **The Brain**: Implement the Blackboard IO connection in a separate script to test storage/retrieval.
3.  **The Voice**: Connect ElevenLabs and test latency.
4.  **The UI**: Polish the visual feedback.
