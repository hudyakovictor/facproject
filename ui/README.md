# DEEPUTIN Forensic Workstation — UI

## Structure

```
ui/
  spec/
    SPEC.md              # Main technical specification (elements, data keys, types)
    API_CONTRACT.md      # API endpoints and response schemas
    DATA_SOURCES.md      # Maps UI elements to exact source files/keys
  mock/
    stage1/              # Mock Stage 1 output (exact schema match)
    stage2/              # Mock Stage 2 output
    stage3/              # Mock Stage 3 output
    api/                 # Mock API responses
  src/                   # Frontend source code (to be created)
  public/                # Static assets (to be created)
```

## Quick Start for Designers

1. Read `spec/SPEC.md` — it lists every UI element with its data key and type.
2. Open `mock/` — these files are your data playground. They have the exact same schema as real data.
3. Design any layout you want. Do NOT invent new data fields.
4. Hand off to developers with your mock data + `SPEC.md`.

## Quick Start for Developers

1. Read `spec/SPEC.md`, `spec/API_CONTRACT.md`, `spec/DATA_SOURCES.md`.
2. Mock data is in `ui/mock/`. Enable with `DEEPUTIN_MOCK_DATA_ROOT=ui/mock`.
3. Build UI components that consume the data keys defined in `SPEC.md`.
4. Connect to real API endpoints (`http://localhost:8000/api/v1/*`) when ready.
5. **Never** change data schemas to fit a design — adapt the design to the data.

## Data Principles

- **No invented values:** If data is missing, show empty state with reason.
- **not_a_verdict:** All displays must include this flag. System shows measurements, not conclusions.
- **Swappable mocks:** Mock data must be replaceable with real data via a single env var.
- **Type safety:** Every data element has a fixed type. No `any` in production code.

## Out of Scope

- Identity verdicts
- Medical diagnoses
- Automated decisions
- Real-time inference in browser
- Multi-user auth
