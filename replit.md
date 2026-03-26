# Workspace

## Overview

pnpm workspace monorepo using TypeScript. Also contains a Django REST Framework API (`artifacts/zenko-api/`) for the Zenko Performance Management Platform.

## Stack

### Node.js (existing)
- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

### Python (Zenko Django API)
- **Python version**: 3.12
- **Framework**: Django 6 + Django REST Framework 3.17
- **Database**: PostgreSQL (shared with Node.js, via psycopg2-binary)
- **Auth**: Token-based (DRF TokenAuthentication)
- **Path**: `artifacts/zenko-api/`
- **Port**: 8000 (dev server)
- **Base URL**: `http://localhost:8000/zenko/api/v1/`

## Structure

```text
artifacts-monorepo/
├── artifacts/              # Deployable applications
│   ├── api-server/         # Express API server (Node.js)
│   └── zenko-api/          # Django REST Framework API (Python)
│       ├── manage.py
│       ├── requirements.txt
│       ├── start.sh        # Migrate + run server
│       ├── zenko/          # Django project settings + urls
│       └── apps/
│           ├── authentication/  # Custom User + Token auth
│           ├── organizations/   # Organization + Membership
│           └── okr/             # Objectives, KeyResults, KeyResultHistory
├── lib/                    # Shared libraries
│   ├── api-spec/           # OpenAPI spec + Orval codegen config
│   ├── api-client-react/   # Generated React Query hooks
│   ├── api-zod/            # Generated Zod schemas from OpenAPI
│   └── db/                 # Drizzle ORM schema + DB connection
├── scripts/                # Utility scripts (single workspace package)
│   └── src/                # Individual .ts scripts, run via `pnpm --filter @workspace/scripts run <script>`
├── pnpm-workspace.yaml     # pnpm workspace (artifacts/*, lib/*, lib/integrations/*, scripts)
├── tsconfig.base.json      # Shared TS options (composite, bundler resolution, es2022)
├── tsconfig.json           # Root TS project references
└── package.json            # Root package with hoisted devDeps
```

## TypeScript & Composite Projects

Every package extends `tsconfig.base.json` which sets `composite: true`. The root `tsconfig.json` lists all packages as project references. This means:

- **Always typecheck from the root** — run `pnpm run typecheck` (which runs `tsc --build --emitDeclarationOnly`). This builds the full dependency graph so that cross-package imports resolve correctly. Running `tsc` inside a single package will fail if its dependencies haven't been built yet.
- **`emitDeclarationOnly`** — we only emit `.d.ts` files during typecheck; actual JS bundling is handled by esbuild/tsx/vite...etc, not `tsc`.
- **Project references** — when package A depends on package B, A's `tsconfig.json` must list B in its `references` array. `tsc --build` uses this to determine build order and skip up-to-date packages.

## Root Scripts

- `pnpm run build` — runs `typecheck` first, then recursively runs `build` in all packages that define it
- `pnpm run typecheck` — runs `tsc --build --emitDeclarationOnly` using project references

## Packages

### `artifacts/api-server` (`@workspace/api-server`)

Express 5 API server. Routes live in `src/routes/` and use `@workspace/api-zod` for request and response validation and `@workspace/db` for persistence.

- Entry: `src/index.ts` — reads `PORT`, starts Express
- App setup: `src/app.ts` — mounts CORS, JSON/urlencoded parsing, routes at `/api`
- Routes: `src/routes/index.ts` mounts sub-routers; `src/routes/health.ts` exposes `GET /health` (full path: `/api/health`)
- Depends on: `@workspace/db`, `@workspace/api-zod`
- `pnpm --filter @workspace/api-server run dev` — run the dev server
- `pnpm --filter @workspace/api-server run build` — production esbuild bundle (`dist/index.cjs`)
- Build bundles an allowlist of deps (express, cors, pg, drizzle-orm, zod, etc.) and externalizes the rest

### `lib/db` (`@workspace/db`)

Database layer using Drizzle ORM with PostgreSQL. Exports a Drizzle client instance and schema models.

- `src/index.ts` — creates a `Pool` + Drizzle instance, exports schema
- `src/schema/index.ts` — barrel re-export of all models
- `src/schema/<modelname>.ts` — table definitions with `drizzle-zod` insert schemas (no models definitions exist right now)
- `drizzle.config.ts` — Drizzle Kit config (requires `DATABASE_URL`, automatically provided by Replit)
- Exports: `.` (pool, db, schema), `./schema` (schema only)

Production migrations are handled by Replit when publishing. In development, we just use `pnpm --filter @workspace/db run push`, and we fallback to `pnpm --filter @workspace/db run push-force`.

### `lib/api-spec` (`@workspace/api-spec`)

Owns the OpenAPI 3.1 spec (`openapi.yaml`) and the Orval config (`orval.config.ts`). Running codegen produces output into two sibling packages:

1. `lib/api-client-react/src/generated/` — React Query hooks + fetch client
2. `lib/api-zod/src/generated/` — Zod schemas

Run codegen: `pnpm --filter @workspace/api-spec run codegen`

### `lib/api-zod` (`@workspace/api-zod`)

Generated Zod schemas from the OpenAPI spec (e.g. `HealthCheckResponse`). Used by `api-server` for response validation.

### `lib/api-client-react` (`@workspace/api-client-react`)

Generated React Query hooks and fetch client from the OpenAPI spec (e.g. `useHealthCheck`, `healthCheck`).

### `scripts` (`@workspace/scripts`)

Utility scripts package. Each script is a `.ts` file in `src/` with a corresponding npm script in `package.json`. Run scripts via `pnpm --filter @workspace/scripts run <script>`. Scripts can import any workspace package (e.g., `@workspace/db`) by adding it as a dependency in `scripts/package.json`.

---

## Zenko API (`artifacts/zenko-api`) — Django REST Framework

The Zenko OKR Core API is a standalone Django REST Framework project for the Zenko Performance Management Platform. It runs on port 8000.

**Start the server:** Workflow "Zenko Django API" runs `bash artifacts/zenko-api/start.sh` (auto-migrates then starts Django dev server).

**Migrations:** `cd artifacts/zenko-api && python3 manage.py makemigrations && python3 manage.py migrate`

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
| POST | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/` | Create KR (weightage overflow blocked) |
| GET  | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/` | List KRs |
| GET  | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/{kr_id}/` | KR detail |
| PATCH| `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/{kr_id}/` | Update KR value (logs history) |
| DELETE| `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/{kr_id}/` | Delete |
| GET  | `/zenko/api/v1/organizations/{org_id}/objectives/{obj_id}/key-results/{kr_id}/history/` | History log |

### Business Rules
- **Objective status lifecycle:** `draft` → `pending_approval` → `approved` / `rejected`. Admins auto-approve on create.
- **Quarter auto-computed** from `due_date` (e.g., due June 30 → Q2-2026).
- **KR weightage validation:** Total cannot exceed 100%. `progress_pct` on Objective is `null` unless KRs sum to exactly 100%.
- **KR RAG status:** auto-computed on value change (not_started → red/amber/green based on progress %).
- **KR history:** Every value/RAG change creates an immutable record.
- **Token header:** `Authorization: Token <token>`

### Roles
| Role | Capabilities |
|------|-------------|
| `app_admin` | All operations across all orgs |
| `org_admin` | Full org access; auto-approves own objectives |
| `hr_manager` | View all + approve/reject objectives |
| `team_lead` | View team + approve/reject objectives |
| `team_member` | Own objectives only; needs approval |
