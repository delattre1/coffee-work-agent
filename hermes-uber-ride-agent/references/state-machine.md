# State machine

`RECEIVED → PARSED → CONTEXT_RESOLVED → AUTHENTICATED → PRODUCT_SELECTED → ESTIMATE_READY → AWAITING_APPROVAL → APPROVED → REQUESTING → REQUESTED/SCHEDULED → DRIVER_ASSIGNED → DRIVER_ARRIVING → IN_PROGRESS → COMPLETED`

Terminal/side states: `AUTH_REQUIRED`, `CANCELED`, `FAILED`. Persist only ride IDs, resolved non-secret context, selected product/fare metadata, approval evidence and current status. Never persist OAuth tokens in ride state.
