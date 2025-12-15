# Instagram Followers Scraper (Web API)

Scrapes Instagram followers using the Web API endpoint (`www.instagram.com/api/v1/`). This method is more stable than the mobile API and has more lenient rate limits.

## How It Works

This actor uses the same API endpoint that Instagram's web interface uses when you view followers. It requires browser session cookies for authentication.

### Advantages over Mobile API
- More lenient rate limits
- Faster response times (~0.3-0.5s per request)
- No device ID fingerprinting
- Works with regular browser session

### Rate Limits
- ~25 followers per request (Instagram's limit)
- Recommended delay: 3 seconds between requests
- 10,000 followers ≈ 400 requests ≈ 20 minutes

## Getting Your Session Cookies

1. Open Instagram in Chrome (logged in)
2. Press F12 → Application → Cookies → instagram.com
3. Copy these values:
   - `sessionid` (required)
   - `csrftoken` (required)
   - `ds_user_id` (recommended)
   - `ig_did` (optional)
   - `mid` (optional)

4. For the `www_claim` header:
   - Open Network tab
   - Navigate to any page on Instagram
   - Find a request to `www.instagram.com/api/`
   - Copy the `X-IG-WWW-Claim` header value

## Input Example

```json
{
    "user_id": "71392995955",
    "session_id": "71392995955%3AABCdef123...",
    "csrf_token": "abcdef123456",
    "ds_user_id": "71392995955",
    "ig_did": "E81EB5F6-41E2-45F0-A52D-4BCA2A643535",
    "mid": "aCcVEAAEAAEcPVNdmW4KWah3dBHd",
    "www_claim": "hmac.AR01V2x7Wz2k...",
    "max_followers": null,
    "delay": 3.0
}
```

## Output

Each follower object contains:

```json
{
    "pk": "12345678",
    "username": "example_user",
    "full_name": "Example User",
    "is_private": false,
    "is_verified": false,
    "profile_pic_url": "https://..."
}
```

## Cookie Expiration

- `sessionid`: ~1 year
- `csrftoken`: ~1 year  
- Other cookies: Various expiration times

The session remains valid as long as you don't log out from that browser session.

## Troubleshooting

### 401 Unauthorized
- Your session cookies have expired
- Get fresh cookies from browser

### 429 Rate Limited
- Increase the delay parameter
- Wait a few minutes before retrying

### Empty Results
- Verify the user_id is correct
- Check if the target account exists and has followers
