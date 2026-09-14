# OAuth

Use OAuth 2.0 Authorization Code for Rider API. Authorization: `https://auth.uber.com/oauth/v2/authorize`; token: `https://auth.uber.com/oauth/v2/token`. Always generate and validate `state`. Store tokens only in macOS Keychain service `com.hermes.uber`. `request` is needed for Ride Requests; `profile` is also configured because `GET /v1.2/me` currently requires it. Guest Rides uses a separate OAuth **client credentials** token with `guests.trips`; it authenticates the application (not the Rider user) and may require Uber business/organization access.
