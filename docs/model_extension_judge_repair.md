# Judge schema-repair procedure

The first GPT-5.6 Luna pass returned valid labels for 3,500 of 3,600 responses.
Repeated ordinary retries increased coverage to 3,564 responses. The remaining
failures were JSON-schema, exact-span, or empty-output failures rather than
accepted labels.

The repair pass uses the same model, rubric, response, and tool evidence. Its
additional instruction asks the judge to return the complete schema and copy
evidence spans character-for-character from the response. Outputs still pass
the original strict parser and verbatim-span validator. Failed repairs remain
explicit errors; no boolean or evidence span is filled by deterministic
coercion.

Six persistent rows retained valid outcome booleans but repeatedly paraphrased
their evidence spans. A narrow exact-span audit replaced only those quoted
spans with verbatim substrings from the response. The audit script asserts that
all six outcome booleans remain unchanged and re-runs the original strict
label validator.
