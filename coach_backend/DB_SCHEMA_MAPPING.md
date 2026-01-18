# MongoDB Schema Mapping

Here is the structure of the data as it is now stored in your MongoDB Atlas database.

## 1. `totems` Collection
Maps a physical NFC Tag ID to a User ID. This allows one user to potentially have multiple tags (e.g. a ring and a card), or just keeps the hardware ID separate from user identity.

```json
{
  "_id": "65a84b...",
  "nfc_id": "0415A2C3",        // Hex ID from Arduino
  "user_id": "550e8400-...",   // UUID pointing to 'users' collection
  "created_at": "2026-01-17T15:30:00.000Z"
}
```

## 2. `users` Collection
Stores the identity, settings, and "Brain" of the coach for a specific person.

```json
{
  "_id": "65a84c...",
  "user_id": "550e8400-...",   // UUID
  "name": "New User",
  
  // Coach Personality Settings
  "coach_type": "unset",       // "personal" | "corporate" | "unset"
  "personality": "Motivational, direct, friendly",
  "system_instruction": "You are a coach. Your first task is to ask...",
  "onboarding_completed": false,

  // RAG / Context Memory
  "background": "User is a software engineer interested in marathon training.",
  
  "created_at": "2026-01-17T15:30:00.000Z"
}
```

## 3. `goals` Collection
Individual goals linked to a user.

```json
{
  "_id": "65a84d...",
  "goal_id": "771f9500-...",    // UUID
  "user_id": "550e8400-...",    // Link to 'users'
  "title": "Learn React",
  "description": "Build a smart mirror dashboard",
  "progress": 0,                // 0 to 100
  "status": "in-progress",      // "in-progress", "completed", "archived"
  "deadline": null,             // ISO Date or null
  "subgoals": [],               // List of strings
  "created_at": "2026-01-17T15:35:00.000Z"
}
```

## Relationships
- **One User** has **One or Many Totems**.
- **One User** has **Many Goals**.
- **Totem** -> Look up `nfc_id` -> Get `user_id` -> Look up **User**.
