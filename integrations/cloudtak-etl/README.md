# etl-wmdplotter — CloudTAK plugin

A [CloudTAK](https://cloudtak.io/) ETL task that pushes WMD PLOTTER CBRN hazard
zones (plume, blast, radiation, BLEVE, dense-gas, fire/smoke) into TAK as styled,
auto-staling drawn shapes — so a plume a responder computes shows up on every
connected ATAK/WinTAK/CloudTAK client on the incident.

This runs **inside** a CloudTAK deployment (it is a CloudTAK "Integration" /
ETL Layer), not inside the WMD PLOTTER server. It is a separate deployable.

## How it works

CloudTAK's plugin model is the `@tak-ps/etl` base class: a task implements
`schema()` + `control()` and calls `this.submit(featureCollection)`; the Layer
fans that out to connected TAK users. This task supports two invocation modes:

```
                    ┌── webhook (event-driven, primary) ──┐
 WMD PLOTTER  ──POST hazard FeatureCollection──►  etl-wmdplotter  ──submit()──►  Layer ──► TAK users
                    └── schedule (optional poll) ─────────┘
```

- **Webhook** (`static webhooks`): WMD PLOTTER POSTs to the layer's webhook URL
  the instant an operator broadcasts. A plume is event-driven and short-lived, so
  this is the right primary path — no polling lag.
- **Schedule** (`control()`, disabled by default): polls a WMD PLOTTER instance
  for active incidents. Use it for a persistent "active incidents" layer.

The WMD → CoT transform ([`transform.js`](transform.js)) is a pure function,
unit-tested off-cloud:

```bash
node transform.test.js      # 17 checks, no CloudTAK/AWS needed
```

It drops non-hazard features (the source marker), passes each contour polygon
through with per-zone stroke/fill styling, builds ATAK remarks in the same house
style as the direct-CoT path (`backend/tak_dp.py`) — `WMD PLOTTER | CHEM INCIDENT
| AGENT: Chlorine | RATE: 50.00 kg/min | WIND: W 6.7 mph | PG-D` — and gives each
zone a **stable id per incident+zone** so re-broadcasting *updates* the CoT in
ATAK instead of stacking duplicates.

## The webhook contract (WMD PLOTTER side)

WMD PLOTTER broadcasts by POSTing to the layer webhook:

```jsonc
POST https://<cloudtak-webhook-url>/broadcast
{
  "meta": {
    "name": "Downtown Chlorine Leak",
    "kind": "chem incident",
    "agent": "Chlorine",
    "rate_kg_min": 50,
    "wind_label": "W 6.7 mph",
    "stability": "D",
    "source_uid": "incident-A",     // stable id → idempotent updates
    "time": "2026-08-12T17:00:00Z"
  },
  "geojson": { /* exactly what /api/plume (or /api/blast, …) returns */ }
}
```

`geojson` is the unmodified WMD model FeatureCollection — no new server work; the
transform reads the properties WMD already emits (`level`, `label`, `color`,
`threshold_ppm`, `max_downwind_km`).

## Deploy

Prereqs: Node 24+, Docker w/ buildx, AWS CLI, access to a CloudTAK environment.

```bash
npm install
npm test                    # transform checks
npx cloudtak-etl            # validates capabilities.json, builds + pushes to ECR
```

Then in the CloudTAK Admin UI (`map.<domain>/admin`): **Integrations → add**,
name it and set the container prefix to match this repo, confirm the version
appears, then create an ETL **Layer** in a Connection. Point the Layer at a
**Mission/channel** to scope the broadcast to the incident's responders rather
than the whole server (CloudTAK supports both).

## Status & caveats

- **`transform.js` is verified** (17/17 off-cloud). **`task.ts` is scaffold** —
  the `submit()` / webhook wiring can only be exercised against a live CloudTAK
  deployment, which needs AWS. Treat it as a faithful-to-the-interface starting
  point, not a tested artifact.
- Interfaces confirmed from source on **2026-08-12**: `@tak-ps/etl`
  (`dfpc-coe/etl-base`) **v10.13.0** — `InvocationType` = {Manual, Schedule,
  Webhook}, `DataFlowType` = {Incoming, Outgoing}, `submit(fc)`, and the
  `static webhooks(schema, task)` route pattern (`@openaddresses/batch-schema`).
  This ecosystem moves fast — **pin versions and re-verify** the webhook body
  contract and `env()`/`submit()` signatures against the installed version
  before relying on it.
- This is a **third TAK distribution path**, complementary to the two WMD PLOTTER
  already has (VPS b-f-t-r data packages for the web app; the standalone app's
  native CoT plugin). It targets orgs already running CloudTAK on AWS.
