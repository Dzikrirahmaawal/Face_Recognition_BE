# Camera Lab (development only)

A dependency-free browser client for testing the face enrollment, identification, liveness, and attendance flow end to end. It uses the kiosk API and is **not** intended for production use.

## Prerequisites

- The API is running, for example at `http://localhost:8000`.
- `CORS_ORIGINS` includes the origin you serve this client from. The default `.env.example` includes `http://localhost:8080` and `http://127.0.0.1:8080`.
- A kiosk device token created by an administrator.
- A browser with camera access. Camera access works on `localhost` or HTTPS, not plain HTTP on a LAN address.

## Run

From the project root:

```bash
python -m http.server 8080 --directory devtools/camera-client
```

Open <http://localhost:8080>.

## Create a kiosk token

```bash
# 1. Log in as a super admin.
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"YourAdminPassword123!"}'

# 2. Use the returned access_token to create a kiosk.
curl -s -X POST http://localhost:8000/api/v1/kiosks \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H 'Content-Type: application/json' \
  -d '{"kiosk_code":"CAM-01","device_name":"Camera Lab","location":"Development"}'
```

Paste the returned `device_token` into the client's **Kiosk token** field. It is returned only once. Store it in a local development secret store, not in source control.

## Flow

1. Set the API base URL and kiosk token, then save.
2. Start the camera.
3. Enroll a consenting test subject.
4. Run **Identify** to test matching. A `MATCHED` result fills the visitor ID.
5. Run **Liveness check** if the configured provider supports it.
6. Use **Check in** / **Check out**. Each click sends an `Idempotency-Key`.

With the default mock providers, images are processed deterministically for workflow testing only. Mock providers are rejected by production configuration validation.

## Safety

- Use only consenting test subjects and non-production data.
- Do not paste production kiosk tokens into shared browsers.
- Do not deploy this directory as part of the production API.
