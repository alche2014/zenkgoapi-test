# Zenko — Performance Management Platform (Backend PRD)

**Version:** 1.0 (Backend Focus)
**Date:** March 26, 2026
**Product Name:** Zenko (zenkohq.com)

---

## 1. Executive Summary

This document defines the backend product requirements for **Zenko**, a comprehensive Performance Management Platform. Zenko enables organizations and consulting firms to measure, track, and optimize performance across multiple dimensions: strategic objectives, team execution, initiative delivery, and leading performance indicators.

The platform supports a multi-tenant data model (isolated by organization), complex hierarchical performance structures, role-based access control, historical trend analysis, and comprehensive APIs for real-time performance visibility and reporting.

The scope of this document is strictly limited to backend business logic, data modeling, API contracts, and background processing. It intentionally omits any frontend implementation details, UI/UX design, or specific framework selections.

---

## 2. Core Business Problem & Solution

### 2.1. The Problem
Organizations struggle to maintain real-time visibility into performance across multiple dimensions simultaneously. Traditional approaches rely on spreadsheets (no historical tracking, no access control, no real-time updates), disconnected tools (fragmented data), or overly complex enterprise systems (difficult to implement and maintain).

### 2.2. The Solution
Zenko provides a unified performance management system that tracks performance through a **four-level hierarchy**:

1. **Strategic Objectives:** What are we trying to achieve?
2. **Key Results:** How will we measure success?
3. **Delivery Initiatives:** What specific work must we execute?
4. **Performance Indicators:** What signals tell us we're on track?

This hierarchy allows organizations to cascade strategy into execution and measure both **leading indicators** (predictive signals during execution) and **lagging indicators** (outcome measurements at the end of a period).

---

## 3. Data Isolation & Multi-Tenancy

### 3.1. Organizational Isolation
The system serves two primary use cases:
*   **Consulting Model:** A consulting firm manages performance for multiple client organizations from a single App Admin account, with complete data isolation between clients.
*   **Enterprise Model:** An organization manages performance internally across departments, teams, and individuals with role-based access control.

**Constraint:** Every data entity must be associated with an `organization_id`. The backend must validate that the authenticated user has an active membership in the requested `organization_id` for every API call.

### 3.2. Visibility Scoping
Users see only the performance data within their scope of responsibility:
*   **App Admin:** Sees all organizations (administrative only).
*   **Org Admin:** Sees all performance data within their organization.
*   **HR Manager:** Sees all performance data within their organization.
*   **Team Lead:** Sees performance data for their direct reports and team members.
*   **Team Member:** Sees their own performance data and performance data for their direct reports (if they are a manager).

**Backend Logic:** Visibility scope is computed via a recursive query on the `manager_id` chain. When a user requests performance data, the backend must determine which organizational units and team members fall under their purview.

---

## 4. Performance Hierarchy & Data Models

### 4.1. Strategic Objectives
**Purpose:** Define what the organization or team is trying to achieve in a given period.

**Fields:**
*   Title (mandatory)
*   Description (optional)
*   Owner (mandatory) - The person accountable for this Objective
*   Priority (mandatory) - High, Medium, Low
*   Quarter (auto-computed from due_date)
*   Due Date (mandatory)
*   Status (draft, pending_approval, approved, rejected, archived)

**Lifecycle:**
*   Team Members create Objectives as `draft`.
*   Submission transitions the Objective to `pending_approval` and notifies the Team Lead.
*   Team Lead or Org Admin approves (→ `approved`) or rejects (→ `rejected`).
*   Objectives created by Org Admin or App Admin are auto-approved.
*   Archived Objectives are hidden from active views but retained for historical reporting.

**Progress Calculation:**
An Objective's overall progress is the **weighted average** of its child Key Results:

```
Objective Progress = Σ (KR Progress % × KR Weightage %) for all KRs
```

This calculation is only valid when all KRs have a weightage assigned and they sum to exactly 100%.

### 4.2. Key Results (KRs)
**Purpose:** Define how success for an Objective will be measured. KRs are quantitative and time-bound.

**Fields:**
*   Title (mandatory)
*   Metric Label (mandatory) - Free-text description of what is measured (e.g., "Monthly Active Users")
*   Type (mandatory) - Numeric, Percentage, Boolean, Currency
*   Start Value (mandatory, default 0)
*   Target Value (mandatory, default 100)
*   Current Value (mandatory, default 0)
*   Unit (optional) - e.g., "$", "%", "users"
*   Owner (mandatory) - The person accountable for this KR
*   Co-Owner (optional) - Supporting owner
*   Due Date (mandatory)
*   Weightage (mandatory) - Integer percentage representing this KR's contribution to the Objective's overall progress
*   RAG Status (mandatory, default "Not Started") - Green, Amber, Red, Not Started

**Weightage Validation (Hard Block):**
The sum of all KR weightages under a single Objective must equal exactly 100%. The backend API must reject any create/update request that violates this rule with a 400 error. The error response must include the current allocation and remaining percentage.

**RAG Status Definitions:**
*   **Green:** On track. Will be delivered by due date with no intervention.
*   **Amber:** At risk. Facing a blocker or behind schedule.
*   **Red:** Off track. Will not be delivered without immediate escalation.
*   **Not Started:** No value logged yet. Default state. A KR with current value = 0 and no history must show "Not Started", never "Green".

**Historical Tracking:**
Every update to a KR's value or RAG status creates an immutable record in `key_result_history` with: previous_value, new_value, previous_rag_status, new_rag_status, note, updated_by, recorded_at.

### 4.3. Key Initiatives (Delivery Initiatives)
**Purpose:** Define the specific, time-bound projects or work streams that will drive progress on the Key Result.

**Fields:**
*   Title (mandatory)
*   Expectations (mandatory) - What does success look like? (replaces generic "Description")
*   Status (mandatory, default "Not Started") - Not Started, In Progress, Completed, Blocked
*   Owner (mandatory) - The person accountable for this Initiative
*   Co-Owner (optional) - Supporting owner
*   Start Date (optional)
*   Due Date (optional)

**Initiative Assessments:**
Two types of assessments can be logged on a Key Initiative:

**Check-in (Periodic Health Update):**
*   Check-in Status: Exceeding Expectations, Meeting Expectations, Below Expectations — Recoverable, Below Expectations — At Risk
*   Summary (mandatory) - Narrative update on progress
*   Assessment Date (mandatory, defaults to today)

**Result (Conclusion Assessment):**
*   Result Status: Succeeded, Partially Succeeded, Failed
*   Summary (mandatory) - Narrative summary of what was achieved
*   Assessment Date (mandatory)
*   Logging a Result automatically sets the Initiative status to "Completed"

**Initiative Health Badge:**
The Initiative's health reflects the worst-case RAG status across all its child KPIs (Red > Amber > Green > Not Started).

**References:**
Each Initiative can have multiple references (files, URLs, or future task management links) stored in the `initiative_references` table. These provide context and supporting documentation.

**Risks:**
Risks are logged at the Initiative level using an Impact × Likelihood matrix (1-5 scales). Risk Score = Impact × Likelihood. Risks with scores ≥ 10 are flagged as "Critical & High Risks" on dashboards.

### 4.4. Performance Indicators (KPIs)
**Purpose:** Provide leading indicators that signal whether a Key Initiative is on track before the quarter ends.

**Characteristics:**
*   Attached to a Key Initiative (not directly to a KR)
*   Measured frequently (daily, weekly, monthly) - more frequent than the parent KR
*   Leading indicators by design (answer: "What signal will tell us this Initiative is working?")
*   Automatically compute RAG status based on measurement type and logged values

**Indicator Type:**
*   **Leading Indicator:** Predictive signal during execution (default)
*   **Lagging Indicator:** Outcome measurement (soft warning on creation if detected)

**13 Measurement Types:**

| Type | Purpose | Key Fields | RAG Logic |
|------|---------|-----------|-----------|
| 1. Absolute (Higher) | Growth metrics | Current, Target | Green ≥ Target; Amber 80-99%; Red < 80% |
| 2. Absolute (Lower) | Reduction metrics | Current, Target, Context Label | Green ≤ Target; Amber 100-120%; Red > 120% |
| 3. % Increase from Baseline | Growth vs starting point | Baseline, Current, Target % | Green ≥ Target%; Amber 80-99%; Red < 80% |
| 4. % of Target | Percentage metrics | Current %, Target % | Green ≥ Target%; Amber 80-99%; Red < 80% |
| 5. Position / Rank | Ranking metrics | Current Position, Target Position | Green ≤ Target; Amber ±1 position; Red > ±1 |
| 6. Ratio | Ratio metrics | Numerator, Denominator, Target Ratio | Green ≥ Target; Amber 80-99%; Red < 80% |
| 7. Benchmark | Comparison to external benchmark | Current, Benchmark, Direction | Green meets benchmark; Amber 90-99%; Red < 90% |
| 8. Period-over-Period | Change vs prior period | Current, Prior Period, Target % Change | Green ≥ Target%; Amber 80-99%; Red < 80% |
| 9. Computed Formula | Multi-variable calculation | Variables A-D, Formula Expression | Computed from formula inputs |
| 10. Compliance / Threshold | Compliance with target | Current, Target, Tolerance Buffer | Green at target; Amber within buffer; Red outside |
| 11. Range / Corridor | Target within a range | Current, Floor, Ceiling | Green within range; Amber at edges; Red outside |
| 12. Milestone / Binary | Yes/No achievement | Target Date, Status | Green = Achieved; Red = Missed |
| 13. Composite Score | Weighted sub-scores | Sub-scores with weights | Green ≥ Target; Amber 80-99%; Red < 80% |

**KPI Fields:**
*   Title (mandatory)
*   Measurement Type (mandatory)
*   Indicator Type (mandatory) - Leading or Lagging
*   Measurement Frequency (mandatory) - Daily, Weekly, Monthly
*   Current Value (mandatory)
*   Target Value (mandatory)
*   Unit (mandatory) - %, $, ₨, €, £, #, Position, Ratio, Score, Days, Hours, or Custom
*   Alert Threshold % (optional) - Early warning threshold independent of RAG bands
*   RAG Status (computed, read-only)

**KPI Alerting:**
When a KPI value is updated:
1. Recompute RAG status based on measurement type
2. If RAG changes to Red → create `rag_turned_red` alert
3. If value breaches `alert_threshold_pct` → create `threshold_breached` alert
4. Notify the Initiative owner and KR Co-Owner (if applicable)

**Overdue Detection (Background Job):**
Daily scan of all active KPIs. If a KPI has not been updated within 2× its measurement frequency:
*   Daily KPI: Overdue after 2 days
*   Weekly KPI: Overdue after 14 days
*   Monthly KPI: Overdue after 60 days

Trigger an `overdue` alert and notify the Initiative owner.

**Historical Tracking:**
Every logged KPI value creates an immutable record in `kpi_history` with: value, prior_period_value, rag_status, recorded_by, recorded_at.

**Sparkline Trend:**
The last 5 logged values are available for inline visualization (5-point trend line, RAG-colored). Sparkline is hidden if fewer than 2 history records exist.

---

## 5. People & Organizational Structure

### 5.1. Organizational Units
Self-referencing hierarchical structure supporting unlimited depth:
*   Department (top level)
*   Sub-department (nested)
*   Team (leaf level)

Users are assigned to an Org Unit, which determines their visibility scope and team membership.

### 5.2. Positions
Job titles separate from system roles. Examples: "Engineering Manager", "Product Lead", "Individual Contributor".

A position has an `is_manager` flag that drives dashboard visibility (managers see their direct reports' performance).

### 5.3. Memberships
Links a User to an Organization, storing:
*   System Role (App Admin, Org Admin, HR Manager, Team Lead, Team Member)
*   Position
*   Org Unit
*   Manager (manager_id for reporting line)
*   Joined Date

---

## 6. API Requirements

All endpoints require authentication and organization-level authorization validation.

### 6.1. Visibility & Scoping
*   `GET /api/v1/orgs/{org_id}/visibility-scope` - Returns hierarchical list of users and org units visible to the authenticated user

### 6.2. Dashboard Aggregation
*   `GET /api/v1/orgs/{org_id}/dashboard/overview` - Top-level performance summary (Objective count, RAG distribution, critical risks)
*   `GET /api/v1/orgs/{org_id}/dashboard/key-results` - KR-level aggregation with progress, RAG status, and trend
*   `GET /api/v1/orgs/{org_id}/dashboard/initiatives` - Initiative and KPI aggregation with health badges and alerts

### 6.3. Entity CRUD
Standard CRUD endpoints for:
*   `/objectives` (with state transition endpoints: submit, approve, reject)
*   `/key-results` (must enforce 100% weightage rule)
*   `/initiatives`
*   `/kpis`

### 6.4. Value Logging & Tracking
*   `POST /api/v1/kpis/{kpi_id}/log` - Log a new KPI value, trigger RAG recomputation, and generate alerts
*   `GET /api/v1/key-results/{kr_id}/history` - Retrieve historical KR value changes
*   `GET /api/v1/kpis/{kpi_id}/history` - Retrieve historical KPI value changes

### 6.5. Reporting & Export
*   `GET /api/v1/reports/pdf` - Generate server-side PDF report of performance hierarchy
*   `POST /api/v1/import/csv` - Bulk import Objectives and KRs from CSV

---

## 7. Background Processing

The backend requires a task queue or scheduler for:

1. **KPI Overdue Detection** - Daily scan of all active KPIs
2. **Alert Notifications** - Asynchronous email/in-app notification delivery
3. **PDF Generation** - Offload heavy PDF rendering to background workers

---

## 8. Performance & Security

*   **N+1 Prevention:** Optimize queries fetching the 4-level hierarchy using joins and prefetching
*   **Caching:** Cache visibility scopes and dashboard aggregations, invalidate on hierarchy changes
*   **Data Validation:** Strict payload validation on all write operations
*   **Encryption:** Sensitive credentials (email provider credentials) encrypted at rest using AES-256-GCM
