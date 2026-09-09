# Workspace API contract

All management endpoints derive `user_id`, `workspace_id`, and role from an
active server-side session and membership. A client-supplied workspace id is a
selector only after the server proves membership; cross-workspace resources
return a non-enumerating denial.

## Roles

| Role | Allowed capabilities |
|---|---|
| Owner | Workspace, members, integrations, policy, all organizer actions |
| Tournament organizer | Tournament lifecycle, manual score, single-player manual DQ, approvals |
| Stream operator | Stations, assigned overlays, stream presentation only |
| Moderator | Call/Ready follow-up and conflicts, no result approval or DQ |
| Viewer | Read-only views allowed by workspace policy |

AI is read-only or proposal-only. It never approves, executes a provider
mutation, performs DQ, or enables auto-DQ. Manual authorized single-player DQ
uses the existing command policy.

## Browser source

An overlay URL uses an opaque station/overlay credential. It returns only that
overlay's public display state. It cannot establish an organizer session, list
resources, or call management endpoints. Revocation and rotation invalidate the
previous credential.
