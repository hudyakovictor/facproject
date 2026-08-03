# Timeline API contract

`GET /api/v1/timeline` → JSON array, `{ photos: [...] }` or `{ items: [...] }`.

Required row fields: `id`, `date`, `t`, `era`, `bucket`, `quality`, `boneScore`, `p0`, `p1`, `p2`. Full shape: `src/data.ts#Photo`.

`bucket` is one of: `left_profile`, `left_deep`, `left_mid`, `left_light`, `frontal`, `right_light`, `right_mid`, `right_deep`, `right_profile`.

The UI rejects invalid rows. If no valid rows are returned, it switches to deterministic demo data and displays `DEMO · НЕ ВЕРДИКТ`.
