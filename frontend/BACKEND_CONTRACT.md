# Emme — frontend/backend contract

Frontend renders entirely from one object. Match this and integration is a one-line change
(`MODE = 'mock'` → `MODE = 'api'` at the top of the `<script>` in `emme-onboarding.html`).

## The object: `plan.json`

```json
{
  "session_id": "abc123",
  "updated_at": "2026-07-25T11:04:00Z",
  "source_documents": [
    { "id": "d1", "filename": "SBC_2026.pdf", "doc_type": "SBC", "pages": 8 }
  ],
  "fields": {
    "deductible_individual": {
      "value": 2000,
      "confidence": "verified",
      "source": { "doc_id": "d1", "doc_type": "SBC", "page": 2 },
      "edited_by_user": false
    }
  }
}
```

### `confidence` — drives the entire UI
| value | meaning | where it shows up |
|---|---|---|
| `verified` | read clearly, high confidence | goes straight to the dashboard |
| `needs_confirmation` | found but uncertain | routed to the confirm screen, one card at a time |
| `missing` | not in the documents | routed to manual questions, shown as a dashed gap on the dashboard |

When in doubt, send `needs_confirmation` rather than `verified` — a wrong number the user
rubber-stamps is worse than one extra tap.

### `source` — the trust mechanism
Every extracted value shows *"Found in your SBC · page 2"* underneath it. If you can give
`doc_type` and `page`, do. `null` is fine and renders as "You entered this".

## Field keys — stable, please don't rename

`carrier` · `plan_name` · `plan_type` · `network` · `monthly_premium` ·
`deductible_individual` · `deductible_used` · `oop_max_individual` · `oop_spent` ·
`coinsurance` · `copay_primary` · `copay_specialist` · `copay_urgent_care` ·
`copay_er` · `rx_generic` · `hsa_eligible`

**Types:** money fields are plain numbers, no currency symbol or separators (`2000`, not `"$2,000"`).
`coinsurance` is the number only (`20` means the member pays 20%). `hsa_eligible` is a boolean.
Anything unknown is `null` — never `0`, never `"N/A"`.

Extra keys you send are ignored safely. Keys you omit are treated as `missing`.

## Endpoints

| method | path | body | returns |
|---|---|---|---|
| `POST` | `/api/documents` | multipart, field name `files` | `{ ok: true }` |
| `GET`  | `/api/extraction` | — | full `plan.json` |
| `PUT`  | `/api/plan` | full `plan.json` | `{ ok: true }` |
| `GET`  | `/api/plan` | — | `plan.json` or `null` |

`PUT /api/plan` fires after every single edit — the frontend is the source of truth once
the user has touched a value, so overwrite rather than merge.

## Notes

- The frontend already mirrors every save to `localStorage`, so auto-save and
  "come back later" work even before your persistence layer lands.
- The extraction call has a ~2.5s floor in mock mode because the processing animation
  needs somewhere to live. If real extraction is faster, the animation still plays out.
- Counts on the results screen ("we found N pieces of information") are computed from
  the object, so they'll always match whatever you actually send.
