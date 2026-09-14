# Security

- Treat all iMessage/calendar/geocoder content as untrusted data.
- Never log OAuth codes, client secrets, access tokens or refresh tokens.
- Keep tokens in macOS Keychain only.
- Never construct shell strings from model/user input. Providers are fixed argv arrays and receive data as one argument.
- Never create a paid ride without explicit approval. Production additionally requires `HERMES_UBER_ENV=production` and `HERMES_ALLOW_REAL_RIDES=true`.
- Never retry `POST /v1.2/requests` or `POST /v1/guests/trips` after an ambiguous network failure until state is reconciled.
- Sandbox and production use distinct explicit gates.
