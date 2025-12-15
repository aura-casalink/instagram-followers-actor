# Instagram Followers Scraper v2 (Mobile API)

Scrapes Instagram followers using the Mobile API endpoint (`i.instagram.com/api/v1/`).

**Updated with headers captured from Frida interception of Instagram Android v409.1.0.49.170**

## What's New in v2

| Feature | v1 | v2 |
|---------|----|----|
| User-Agent | Instagram 330.x | Instagram 409.x ✅ |
| X-IG-Capabilities | `3brTvx0=` | `3brTv10=` ✅ |
| X-IG-WWW-Claim | ❌ Not included | ✅ HMAC token |
| X-IG-Nav-Chain | ❌ Not included | ✅ Simulated |
| X-IG-Family-Device-ID | ❌ Not included | ✅ Included |
| X-IG-SALT-IDS | ❌ Not included | ✅ Randomized |
| X-IG-Bandwidth-* | ❌ Not included | ✅ Simulated |
| X-IG-VALIDATE-NULL-* | ❌ Not included | ✅ Included |
| X-IG-Device-Languages | ❌ Not included | ✅ Included |
| Delay | Fixed | Randomized range ✅ |

## Getting Credentials with Frida

### Prerequisites

```bash
# Install Frida
pip install frida-tools

# Android emulator or rooted device with frida-server running
```

### Capture Credentials

1. Start Frida with the capture script:

```bash
frida -U -f com.instagram.android -l frida_followers_capture.js
```

2. In Instagram app:
   - Go to your profile
   - Tap on "Followers"

3. The script will print credentials in this format:

```python
CREDENTIALS = {
    "authorization_token": "IGT:2:eyJ...",
    "device_id": "c6dfb4fc-7663-46a8-8633-fd77d4dfe168",
    "android_id": "android-acd484febac47e6b",
    "family_device_id": "4d8511b5-b0fe-46a1-aef0-1ba731e6d394",
    "www_claim": "hmac.AR0whHhd26sGoKFlEOpIzAA3mPI9c5-4oorEzCbGTpYeZrGJ",
    "user_id": "71392995955",
}
```

4. Copy these values to the actor input.

## Input Example

```json
{
    "user_id": "71392995955",
    "authorization": "IGT:2:eyJkc191c2VyX2lkIjoiNzEzOTI5OTU5NTUi...",
    "device_id": "c6dfb4fc-7663-46a8-8633-fd77d4dfe168",
    "android_id": "android-acd484febac47e6b",
    "family_device_id": "4d8511b5-b0fe-46a1-aef0-1ba731e6d394",
    "www_claim": "hmac.AR0whHhd26sGoKFlEOpIzAA3mPI9c5-4oorEzCbGTpYeZrGJ",
    "max_followers": null,
    "delay_min": 2.0,
    "delay_max": 5.0
}
```

## Output

Each follower object contains:

```json
{
    "pk": "12345678",
    "pk_id": "12345678",
    "username": "example_user",
    "full_name": "Example User",
    "is_private": false,
    "is_verified": false,
    "profile_pic_url": "https://...",
    "has_anonymous_profile_picture": false
}
```

## Important Notes

### WWW-Claim is Critical

The `www_claim` header is an HMAC that Instagram validates server-side. Without it, you're more likely to get blocked.

- It changes with each session
- Capture it fresh before each scraping session
- If you get 401 errors, refresh your credentials

### Keep Device IDs Consistent

Use the same `device_id`, `android_id`, and `family_device_id` across sessions to appear as the same device.

### Rate Limiting

- Default delay: 2-5 seconds (randomized)
- Instagram allows ~100 followers per request
- 10,000 followers ≈ 100 requests ≈ 5-10 minutes

## Troubleshooting

### 401 Unauthorized
- Authorization token expired
- WWW-Claim expired
- **Solution**: Capture fresh credentials with Frida

### 429 Rate Limited
- Too many requests
- **Solution**: The actor will automatically wait and retry

### 400 Bad Request
- Malformed headers
- **Solution**: Verify all credential fields are complete

### Empty Results
- User ID doesn't exist
- Account has no followers
- **Solution**: Verify user_id is correct

## Frida Capture Script

Save this as `frida_followers_capture.js`:

```javascript
Java.perform(function() {
    // Hook OkHttp to capture followers endpoint
    var RealCall = Java.use('okhttp3.RealCall');
    
    RealCall.execute.implementation = function() {
        var request = this.request();
        var url = request.url().toString();
        
        if (url.indexOf('/friendships/') !== -1 && url.indexOf('/followers') !== -1) {
            console.log("\n[FOLLOWERS ENDPOINT]");
            console.log("URL: " + url);
            
            var headers = request.headers();
            for (var i = 0; i < headers.size(); i++) {
                console.log(headers.name(i) + ": " + headers.value(i));
            }
        }
        
        return this.execute();
    };
});
```

## Local Testing

```bash
# Install dependencies
pip install apify requests

# Run locally
python -m src.main
```
