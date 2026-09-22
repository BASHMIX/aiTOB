# Validation Quickstart: Player Profiles

1. Set `DATABASE_URL` and point `AITOB_PG_TEST_URL` at a disposable PostgreSQL database.
2. Run focused profile, presentation, participant review, and broadcast tests:

   ```powershell
   python -m pytest backend/tests/test_player_profile_*.py backend/tests/test_player_presentation_*.py backend/tests/test_broadcast_projection.py -q
   ```

3. Build the organizer UI:

   ```powershell
   Set-Location frontend-react
   npm test
   npm run build
   ```

4. Link an existing player to a new entrant and verify their stored avatar
   appears without re-uploading. Select a character, reload, and verify it is
   retained only in the intended event.
5. Load an existing active station/OBS overlay and verify its response and live
   match remain unchanged before and after profile work.
