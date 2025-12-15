"""
Instagram Followers Scraper - Apify Actor
"""

import asyncio
import requests
import json
import time
from datetime import datetime
from apify import Actor


class InstagramScraper:
    def __init__(self, authorization_token: str, cookies: dict):
        self.session = requests.Session()
        self.base_url = "https://i.instagram.com/api/v1"
        
        # Asegurar formato correcto del token
        if not authorization_token.startswith("Bearer "):
            authorization_token = f"Bearer {authorization_token}"
        
        self.headers = {
            "User-Agent": "Instagram 330.0.0.40.92 Android (34/14; 420dpi; 1080x2400; Google/google; sdk_gphone64_arm64; emu64a; ranchu; en_US; 598323397)",
            "X-IG-App-ID": "567067343352427",
            "X-IG-Device-ID": "android-1234567890abcdef",
            "X-IG-Android-ID": "android-1234567890abcdef",
            "X-IG-Connection-Type": "WIFI",
            "X-IG-Capabilities": "3brTvx0=",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Host": "i.instagram.com",
            "Authorization": authorization_token,
        }
        
        # Set cookies
        for key, value in cookies.items():
            if value:
                self.session.cookies.set(key, value, domain=".instagram.com")
    
    def get_followers(self, user_id: str, max_id: str = None) -> dict:
        url = f"{self.base_url}/friendships/{user_id}/followers/"
        
        params = {"count": 100, "search_surface": "follow_list_page"}
        if max_id:
            params["max_id"] = max_id
        
        Actor.log.info(f"Requesting: {url}")
        response = self.session.get(url, headers=self.headers, params=params)
        
        Actor.log.info(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            Actor.log.error(f"Error response: {response.text[:500]}")
            return None
            
        return response.json()

    def get_all_followers(self, user_id: str, max_followers: int = None, delay: float = 2.0) -> list:
        all_followers = []
        max_id = None
        page = 1
        
        while True:
            Actor.log.info(f"Fetching page {page}...")
            data = self.get_followers(user_id, max_id)
            
            if not data:
                Actor.log.warning("No data returned")
                break
                
            if "users" not in data:
                Actor.log.warning(f"No users in response: {json.dumps(data)[:500]}")
                break
                
            followers = data["users"]
            all_followers.extend(followers)
            
            Actor.log.info(f"Got {len(followers)} followers. Total: {len(all_followers)}")
            
            if max_followers and len(all_followers) >= max_followers:
                Actor.log.info(f"Reached max_followers limit: {max_followers}")
                all_followers = all_followers[:max_followers]
                break
            
            max_id = data.get("next_max_id")
            if not max_id:
                Actor.log.info("No more pages")
                break
            
            page += 1
            time.sleep(delay)
            
        return all_followers


async def main():
    async with Actor:
        # Get input
        actor_input = await Actor.get_input() or {}
        
        user_id = actor_input.get("user_id")
        authorization_token = actor_input.get("authorization_token", "")
        max_followers = actor_input.get("max_followers")
        delay = actor_input.get("delay", 2.0)
        webhook_url = actor_input.get("webhook_url")
        
        # Cookies
        cookies = {
            "x-mid": actor_input.get("cookie_x_mid", ""),
            "ig-u-ds-user-id": actor_input.get("cookie_ds_user_id", ""),
            "ig-u-rur": actor_input.get("cookie_rur", ""),
        }
        
        # Log inputs
        Actor.log.info(f"user_id: {user_id}")
        Actor.log.info(f"authorization_token length: {len(authorization_token)}")
        Actor.log.info(f"max_followers: {max_followers}")
        Actor.log.info(f"delay: {delay}")
        
        # Validate required inputs
        if not user_id:
            raise ValueError("user_id is required")
        if not authorization_token:
            raise ValueError("authorization_token is required")
        
        Actor.log.info(f"Starting Instagram Followers Scraper for user_id: {user_id}")
        
        # Initialize scraper
        scraper = InstagramScraper(authorization_token, cookies)
        
        # Scrape followers
        followers = scraper.get_all_followers(user_id, max_followers, delay)
        
        Actor.log.info(f"Scraped {len(followers)} followers total")
        
        # Save to dataset
        for follower in followers:
            await Actor.push_data({
                "pk": follower.get("pk"),
                "username": follower.get("username"),
                "full_name": follower.get("full_name", ""),
                "is_private": follower.get("is_private", False),
                "is_verified": follower.get("is_verified", False),
                "profile_pic_url": follower.get("profile_pic_url", ""),
                "scraped_at": datetime.now().isoformat(),
            })
        
        # Save summary
        await Actor.set_value("summary", {
            "user_id": user_id,
            "total_followers": len(followers),
            "scraped_at": datetime.now().isoformat(),
        })
        
        # Webhook
        if webhook_url and len(followers) > 0:
            try:
                requests.post(webhook_url, json={
                    "event": "followers_scraped",
                    "user_id": user_id,
                    "total_followers": len(followers),
                    "scraped_at": datetime.now().isoformat(),
                }, timeout=10)
                Actor.log.info(f"Webhook sent to {webhook_url}")
            except Exception as e:
                Actor.log.error(f"Webhook failed: {e}")
        
        Actor.log.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
