# Role
You are a Senior System Architect.

# Task
Create a "Tournament Hub" inside the Admin Dashboard to manage multiple tournaments and stream slots.

# Core Logic
1. **Tournament Registry:**
   - Add a field: "Add Tournament by Start.gg Slug".
   - When a slug is entered, use the Start.gg API to fetch: Tournament Name, Event Name, Game Type (SF6/Tekken), and Participant List.
   - Store these in the `tournaments` table.

2. **Stream Slot Management:**
   - Create a way to define "Stream Slots" (e.g., Stream 1, Stream 2).
   - Allow the TO to "Map" a tournament to a Stream Slot.
   - **Crucial:** In the Match Queue, add buttons for each ready match: "Assign to Stream 1" and "Assign to Stream 2".
   - When assigned, the system must update the `OverlayState` for THAT specific stream slot.

3. **Discord Context:**
   - When a match is assigned to a stream, the Discord Bot's call message must include the stream name: 
     "📢 Match Called: <@P1> VS <@P2>. Please join **Stream 1** lobby."

4. **Status & History:**
   - Ensure that even if two tournaments use the same "Stream 1", the results are saved correctly to their respective tournament slugs in the database based on the `set_id`.

# UI Requirements
- Use a `Select` menu in the dashboard to switch between viewing different tournaments.
- Add a "Refresh Data" button next to each tournament to re-sync participant lists or registration status from Start.gg.