#!/usr/bin/env python3
"""
Instagram Mobile API Followers Scraper v2
Uses i.instagram.com with Bearer token (Android app simulation)

Updated with headers from Frida interception - Instagram 409.1.0.49.170
"""

import asyncio
import requests
import time
import random
from apify import Actor


class InstagramMobileAPI:
    """Instagram Mobile API client with full header simulation"""
    
    def __init__(
        self,
        authorization: str,
        device_id: str,
        android_id: str,
        family_device_id: str = None,
        www_claim: str = None,
        user_id: str = None,
    ):
        self.session = requests.Session()
        self.base_url = "https://i.instagram.com/api/v1"
        
        # Device identifiers
        self.device_id = device_id
        self.android_id = android_id
        self.family_device_id = family_device_id or device_id
        self.user_id = user_id or ""
        
        # Session values
        self.authorization = authorization if authorization.startswith("Bearer ") else f"Bearer {authorization}"
        self.www_claim = www_claim or ""
        
        # Request tracking for nav chain
        self.session_start = time.time()
        self.request_count = 0
        
        self._setup_session()
    
    def _setup_session(self):
        """Configure session with base headers"""
        self.base_headers = {
            # App identification - Updated to v409
            "User-Agent": "Instagram 409.1.0.49.170 Android (34/14; 420dpi; 1080x2219; Google/google; sdk_gphone64_arm64; emu64a; ranchu; en_US; 843192238)",
            "X-IG-App-ID": "567067343352427",
            "X-IG-Capabilities": "3brTv10=",  # Fixed: was 3brTvx0=
            
            # Device identification
            "X-IG-Device-ID": self.device_id,
            "X-IG-Android-ID": self.android_id,
            "X-IG-Family-Device-ID": self.family_device_id,
            
            # Locale settings
            "X-IG-App-Locale": "en_US",
            "X-IG-Device-Locale": "en_US",
            "X-IG-Mapped-Locale": "en_US",
            "X-IG-Device-Languages": '{"system_languages":"en-US"}',
            "Accept-Language": "en-US,en;q=0.9",
            
            # Connection info
            "X-IG-Connection-Type": "WIFI",
            "X-IG-Timezone-Offset": "3600",
            
            # Device capabilities
            "X-IG-Is-Foldable": "false",
            
            # Validation flags (critical for newer versions)
            "X-IG-VALIDATE-NULL-IN-LEGACY-DICT": "true",
            
            # Encoding
            "Accept-Encoding": "gzip, deflate",
            "Host": "i.instagram.com",
            
            # Authorization
            "Authorization": self.authorization,
        }
        
        # Add WWW-Claim if provided (critical for avoiding blocks)
        if self.www_claim:
            self.base_headers["X-IG-WWW-Claim"] = self.www_claim
        
        self.session.headers.update(self.base_headers)
    
    def _get_dynamic_headers(self) -> dict:
        """Generate dynamic headers for each request"""
        self.request_count += 1
        timestamp = f"{time.time():.3f}"
        
        headers = {
            # Bandwidth simulation (varies per request)
            "X-IG-Bandwidth-Speed-KBPS": f"{random.uniform(3000, 8000):.3f}",
            "X-IG-Bandwidth-TotalBytes-B": "0",
            "X-IG-Bandwidth-TotalTime-MS": "0",
            
            # Navigation chain (simulates user navigation)
            "X-IG-Nav-Chain": f"SelfFragment:self_profile:1:main_profile:{self.session_start:.3f}:::{self.session_start:.3f},FollowersFollowingFragment:self_followers:2:button:{timestamp}:::{timestamp}",
            "X-IG-CLIENT-ENDPOINT": "FollowersFollowingFragment:self_followers",
            
            # Salt IDs (experiment/feature flags)
            "X-IG-SALT-IDS": self._get_salt_ids(),
        }
        
        return headers
    
    def _get_salt_ids(self) -> str:
        """Generate SALT IDs - these are experiment flags from the app"""
        salts = ["332011630", "974457404", "974460658"]
        return ",".join(random.sample(salts, k=random.randint(1, len(salts))))
    
    def get_followers(self, user_id: str, max_id: str = None) -> dict:
        """Fetch a page of followers"""
        url = f"{self.base_url}/friendships/{user_id}/followers/"
        
        params = {
            "count": 100,
            "search_surface": "follow_list_page",
        }
        if max_id:
            params["max_id"] = max_id
        
        # Merge base + dynamic headers
        headers = {**self.session.headers, **self._get_dynamic_headers()}
        
        response = self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=30
        )
        
        return {
            "status_code": response.status_code,
            "data": response.json() if response.status_code == 200 else None,
            "text": response.text[:500] if response.status_code != 200 else None,
        }


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        
        # Required inputs
        user_id = actor_input.get("user_id")
        authorization = actor_input.get("authorization")
        
        # Device identifiers (from Frida capture)
        device_id = actor_input.get("device_id", "c6dfb4fc-7663-46a8-8633-fd77d4dfe168")
        android_id = actor_input.get("android_id", "android-acd484febac47e6b")
        family_device_id = actor_input.get("family_device_id", "4d8511b5-b0fe-46a1-aef0-1ba731e6d394")
        
        # Session values (important for avoiding detection)
        www_claim = actor_input.get("www_claim", "")
        
        # Scraping options
        max_followers = actor_input.get("max_followers")
        delay_min = actor_input.get("delay_min", 2.0)
        delay_max = actor_input.get("delay_max", 5.0)
        
        # Validation
        if not user_id or not authorization:
            Actor.log.error("Missing required inputs: user_id, authorization")
            await Actor.fail(status_message="Missing required inputs")
            return
        
        # Log configuration
        Actor.log.info("=" * 60)
        Actor.log.info("Instagram Mobile API Scraper v2")
        Actor.log.info("Headers updated from Frida interception")
        Actor.log.info("=" * 60)
        Actor.log.info(f"Target user_id: {user_id}")
        Actor.log.info(f"Device ID: {device_id[:8]}...")
        Actor.log.info(f"Android ID: {android_id}")
        Actor.log.info(f"WWW-Claim: {'✓ Provided' if www_claim else '✗ Not provided (may cause blocks)'}")
        Actor.log.info(f"Max followers: {max_followers or 'unlimited'}")
        Actor.log.info(f"Delay: {delay_min}-{delay_max}s (randomized)")
        Actor.log.info("=" * 60)
        
        # Initialize API client
        api = InstagramMobileAPI(
            authorization=authorization,
            device_id=device_id,
            android_id=android_id,
            family_device_id=family_device_id,
            www_claim=www_claim,
            user_id=user_id,
        )
        
        # Scraping loop
        all_followers = []
        max_id = None
        page = 0
        total_request_time = 0
        start_time = time.time()
        consecutive_errors = 0
        
        while True:
            page += 1
            
            try:
                req_start = time.time()
                result = api.get_followers(user_id, max_id)
                req_time = time.time() - req_start
                total_request_time += req_time
                
                status = result["status_code"]
                Actor.log.info(f"Page {page}: HTTP {status} | {req_time:.2f}s")
                
                if status == 200:
                    consecutive_errors = 0
                    data = result["data"]
                    users = data.get("users", [])
                    
                    for user in users:
                        all_followers.append({
                            "pk": str(user.get("pk")),
                            "pk_id": str(user.get("pk_id", user.get("pk"))),
                            "username": user.get("username"),
                            "full_name": user.get("full_name", ""),
                            "is_private": user.get("is_private", False),
                            "is_verified": user.get("is_verified", False),
                            "profile_pic_url": user.get("profile_pic_url", ""),
                            "has_anonymous_profile_picture": user.get("has_anonymous_profile_picture", False),
                        })
                    
                    Actor.log.info(f"  → Got {len(users)} followers (total: {len(all_followers)})")
                    
                    # Check for next page
                    max_id = data.get("next_max_id")
                    if not max_id:
                        Actor.log.info("✓ Reached end of followers list")
                        break
                    
                    # Check max limit
                    if max_followers and len(all_followers) >= max_followers:
                        Actor.log.info(f"✓ Reached max limit: {max_followers}")
                        break
                
                elif status == 401:
                    consecutive_errors += 1
                    error_text = result.get("text", "")
                    Actor.log.error(f"Auth error (401): {error_text[:200]}")
                    
                    # Check if it's a rate limit disguised as 401
                    if "wait" in error_text.lower() or "espera" in error_text.lower() or "please wait" in error_text.lower():
                        wait_time = 30 + (consecutive_errors * 15)
                        Actor.log.warning(f"Rate limited via 401, waiting {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        await Actor.fail(status_message="Authorization failed - token may be expired")
                        return
                
                elif status == 429:
                    consecutive_errors += 1
                    wait_time = 60 + (consecutive_errors * 30)
                    Actor.log.warning(f"Rate limited (429), waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                
                elif status == 400:
                    consecutive_errors += 1
                    Actor.log.error(f"Bad request (400): {result.get('text', '')[:200]}")
                    
                    if consecutive_errors >= 3:
                        Actor.log.error("Too many consecutive errors, stopping")
                        break
                    
                    await asyncio.sleep(10)
                    continue
                
                else:
                    consecutive_errors += 1
                    Actor.log.error(f"Unexpected error ({status}): {result.get('text', '')[:200]}")
                    
                    if consecutive_errors >= 3:
                        Actor.log.error("Too many consecutive errors, stopping")
                        break
                    
                    await asyncio.sleep(5)
                    continue
                    
            except requests.exceptions.Timeout:
                consecutive_errors += 1
                Actor.log.warning(f"Request timeout, attempt {consecutive_errors}/3")
                if consecutive_errors >= 3:
                    break
                await asyncio.sleep(10)
                continue
                
            except requests.exceptions.RequestException as e:
                consecutive_errors += 1
                Actor.log.error(f"Request exception: {e}")
                if consecutive_errors >= 3:
                    break
                await asyncio.sleep(5)
                continue
                
            except Exception as e:
                Actor.log.error(f"Unexpected exception: {e}")
                break
            
            # Random delay between requests
            delay = random.uniform(delay_min, delay_max)
            await asyncio.sleep(delay)
        
        # Summary
        total_time = time.time() - start_time
        
        Actor.log.info("")
        Actor.log.info("=" * 60)
        Actor.log.info("SCRAPING COMPLETE")
        Actor.log.info("=" * 60)
        Actor.log.info(f"Total followers scraped: {len(all_followers)}")
        Actor.log.info(f"Total pages fetched: {page}")
        Actor.log.info(f"Total time: {total_time:.1f}s")
        Actor.log.info(f"Request time (network): {total_request_time:.1f}s")
        Actor.log.info(f"Average per page: {total_time/max(page,1):.2f}s")
        Actor.log.info(f"Throughput: {len(all_followers)/max(total_time,1):.1f} followers/second")
        Actor.log.info("=" * 60)
        
        # Push results
        if all_followers:
            if max_followers:
                all_followers = all_followers[:max_followers]
            await Actor.push_data(all_followers)
            Actor.log.info(f"✓ Pushed {len(all_followers)} followers to dataset")
        else:
            Actor.log.warning("No followers collected")


if __name__ == "__main__":
    asyncio.run(main())
