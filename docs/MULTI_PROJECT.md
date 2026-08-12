# Multi-Project Collaboration

LBRO supports **one user → many projects** and **one project → many users** via project membership.

## Authorization model

```
User → ProjectMembership → Project → Project Data (incidents, evidence, API keys, …)
```

- **Platform roles** (`super_admin`, `admin`, …) control global access.
- **Project roles** (`admin`, `analyst`, `viewer`) control access within a project.
- The server always derives the authenticated user from JWT — never trust `project_id` or `role` from the client alone.

## Typical workflow

1. **Register** — public self-service registration stays enabled.
2. **Create a project** — you become **Owner** (implicit admin) with an owner membership row.
3. **Generate API key** — project-scoped `proj_*` key for event/incident ingestion.
4. **Download SDK** — Integrations → Python SDK zip (placeholder key only).
5. **Invite teammates** — Project Settings → Members → enter email + role.
6. **Share invite token** — email is not sent unless SMTP is configured; copy the one-time token.
7. **Accept invitation** — invitee logs in (or registers with the same email) and accepts from the banner.
8. **Switch projects** — navbar project switcher clears cached data and reloads the dashboard.

## Project roles

| Role | View data | Investigate | Manage members / API keys |
|------|-----------|-------------|---------------------------|
| Owner / Admin | ✓ | ✓ | ✓ |
| Analyst | ✓ | ✓ | ✗ |
| Viewer | ✓ | read-only | ✗ |

## Super Admin

Platform Super Admins see all projects for global monitoring. This is separate from project membership.
