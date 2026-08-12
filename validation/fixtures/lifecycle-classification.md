# Managed lifecycle classification fixtures

The fixtures are compact facts for the pure classifier (`classify_facts`):

```text
PRODUCT_FEATURE: branch, registration, spec branch, and feature directory correspond.
NON_PRODUCT: changed paths are declared workflow/infrastructure paths, with no matching feature state.
UNKNOWN: neither positive classification evidence set is complete.
```

The current `agent-sdlc-v2` branch is verified separately from repository facts and must classify as `NON_PRODUCT` with `NOT_APPLICABLE`.
