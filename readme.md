# Zenko — Performance Management Platform

## Overview

Backend-only REST API built with Django REST Framework. No frontend.

## Stack

- **Python version**: 3.12
- **Framework**: Django 6 + Django REST Framework 3.17
- **Database**: PostgreSQL (via `DATABASE_URL` env var, parsed with `urllib.parse`)
- **Auth**: Token-based (`Authorization: Token <token>`)
- **Path**: `artifacts/zenko-api/`
- **Port**: 8000 (dev server)

## Project Structure

```text
artifacts/zenko-api/
├── manage.py
├── requirements.txt
├── start.sh              # Runs migrations then starts the dev server
├── zenko/                # Django project (settings, root urls)
└── apps/
    ├── authentication/   # Custom User model + token auth endpoints
    ├── organizations/    # Organization + Membership models & endpoints
    └── okr/              # Objective, KeyResult, KeyResultHistory models & endpoints
```

## Running Locally

The `Zenko Django API` workflow handles this automatically:

```bash
bash artifacts/zenko-api/start.sh
```

It runs `migrate` then starts the dev server on port 8000.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection URL |
| `DJANGO_SECRET_KEY` | Django secret key (auto-generated fallback in dev) |
| `DEBUG` | `true` to enable debug mode (default: `false`) |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | Comma-separated CORS origins |

---

## API Reference

### API Base URL (development)
`http://localhost:8000/zenko/api/v1/`

### Authentication Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/zenko/api/v1/auth/register/` | None | Register + get token |
| POST | `/zenko/api/v1/auth/login/` | None | Login + get token |
| POST | `/zenko/api/v1/auth/logout/` | Token | Invalidate token |
| GET  | `/zenko/api/v1/auth/me/` | Token | Current user info |

### Organization Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/zenko/api/v1/organizations/` | Create org (creator = Org Admin) |
| GET  | `/zenko/api/v1/organizations/` | List my organizations |
| GET  | `/zenko/api/v1/organizations/{org_id}/` | Org detail |
| POST | `/zenko/api/v1/organizations/{org_id}/members/` | Add member with role |
| GET  | `/zenko/api/v1/organizations/{org_id}/members/` | List members |
| GET  | `/zenko/api/v1/organizations/{org_id}/members/{member_id}/` | Member detail |
| PATCH| `/zenko/api/v1/organizations/{org_id}/members/{member_id}/` | Update member role |
| DELETE| `/zenko/api/v1/organizations/{org_id}/members/{member_id}/` | Remove member |

### Objective Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/zenko/api/v1/organizations/{org_id}/objectives/` | Create (draft or auto-approved for admins) |
| GET  | `/zenko/api/v1/organizations/{org_id}/objectives/` | List active objectives |
| GET  | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/` | Detail with KRs + progress |
| PATCH| `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/` | Update |
| DELETE| `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/` | Delete |
| POST | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/submit/` | Submit for approval |
| POST | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/approve/` | Approve |
| POST | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/reject/` | Reject (requires `reason`) |
| POST | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/archive/` | Archive |

### Key Result Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/` | Create single KR — total including new KR must equal exactly 100% |
| GET  | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/` | List KRs |
| PUT  | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/bulk/` | Atomically replace all KRs (array body, total must == 100%) |
| GET  | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/{kr_id}/` | KR detail |
| PATCH| `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/{kr_id}/` | Update KR (total must remain == 100%) |
| DELETE| `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/{kr_id}/` | Delete |
| GET  | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/{kr_id}/history/` | History log |

### Business Rules
- **Objective status lifecycle:** `draft` → `pending_approval` → `approved` / `rejected`. Org admins auto-approve on CREATE.
- **Quarter auto-computed** from `due_date` (e.g., due June 30 → Q2-2026).
- **KR weightage on individual create/update:** The cumulative total (including the new/updated KR) must equal exactly 100%. Use the bulk PUT endpoint to atomically define multiple KRs.
- **KR weightage at submit:** When submitting an objective for approval, all KR weightages must sum to exactly 100% or the submit is rejected with a 400.
- **progress_pct on Objective:** Returns `null` unless KR weightages sum to exactly 100%.
- **KR RAG status:** auto-computed on value change (not_started → red/amber/green based on progress %).
- **KR history:** Every value/RAG change creates an immutable record.
- **Token header:** `Authorization: Token <token>`

### Roles
| Role | Capabilities |
|------|-------------|
| `app_admin` | All operations across all orgs (cannot approve/reject objectives) |
| `org_admin` | Full org access; auto-approves objectives on CREATE; can approve/reject |
| `hr_manager` | View all; cannot approve/reject objectives |
| `team_lead` | View team; can approve/reject objectives |
| `team_member` | Own objectives only; needs approval |

## Postman Collection

A ready-to-import Postman collection covering all endpoints is at:

```
artifacts/zenko-api/Zenko_OKR_API.postman_collection.json
```

Import via **File → Import** in Postman. Set `base_url` to `http://localhost:8000` and run **Register** first — the token, org_id, obj_id, kr_id, and member_id variables are captured automatically by test scripts on the relevant responses.
