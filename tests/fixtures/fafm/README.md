# Step 3 corpus fixtures

Sourced from `faf` conformance suite (`conformance/fafm/valid/`) on 2026-07-22.

| File | Role |
|------|------|
| `voice.fafm` | Voice profile — bare + tagged facts |
| `knowledge.fafm` | Knowledge profile — index + fact extras (`confidence_score`, `verification_status`) |
| `unknown-fields.fafm` | Fact-level unknown (`experimental_attr`) + top-level `future_root_field` (Step 2.5 residual preserve) |

`from_claude_dir` converted third fixture → Step 4.
