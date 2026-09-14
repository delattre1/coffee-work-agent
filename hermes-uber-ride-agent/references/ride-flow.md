# Immediate ride flow

1. Resolve pickup + destination. 2. OAuth token. 3. `GET /v1.2/products`. 4. Select a returned product; never invent a product ID. 5. `POST /v1.2/requests/estimate`. 6. Reject null pickup estimate/no drivers. 7. Present fare + ETA. 8. Record approval bound to pickup, destination, product and fare. 9. If fare expired (documented ~2 min), re-estimate and require approval again if materially changed. 10. `POST /v1.2/requests`. Never automatically retry an ambiguous request write after timeout.
