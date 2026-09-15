# M2-P5A evidence integrity correction

Commit `6b41b6702b697c641031c28beb9acbe1bc4e5bf1` was pushed even though the staged whitespace gate had failed because the surrounding shell sequence did not stop.

This correction does not alter source, tests, RED semantics, or lifecycle. Textual evidence is normalized for newlines, BOM, and trailing whitespace. `commands.jsonl` is converted to valid NDJSON. The secret scan is rerun after final evidence-byte corrections, evidence hashes are regenerated, and cumulative whitespace checks are rerun from `0b24150b2d013f8836879a64ae3887ec0d72d3b9`.

Independent audit remains required. Status remains `M2-P5A_RED_READY_FOR_REVIEW`.
