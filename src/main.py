"""
Instagram Followers Scraper - Apify Actor
"""

import asyncio
import requests
import json
import time
import random
from datetime import datetime
from apify import Actor


class InstagramScraper:
    def __init__(self, authorization_token: str, cookies: dict):
        self.session = requests.Session()
        self.base_url = "https://i.instagram.com/api/v1"
        
        if not authorization_token.startswith("Bearer "):
            authorization_token = f"Bearer {authorization_token}"
        
        self.headers = {
            "User-Agent": "Instagram 330.0.0.40.92 Android (34/14; 420dpi; 1080x2400; Google/google; sdk_gphone64_arm64; emu64a; ranchu; en_US; 598323397)",
            "X-IG-App-ID": "567067343352427",
            "X-IG-Device-ID": "android-acd484febac47e6b",
            "X-IG-Android-ID": "android-acd484febac47e6b",
            "X-IG-Connection-Type": "WIFI",
            "X-IG-Capabilities": "3brTvx0=",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Host": "i.instagram.com",
            "Authorization": authorization_token,
        }
        
        for key, value in cookies.items():
            if value:
                self.session.cookies.set(key, value, domain=".instagram.com")
    
    def get_followers(self, user_id: str, max_id: str = None) -> tuple:
        """Returns (response, request_time_seconds)"""
        url = f"{self.base_url}/friendships/{user_id}/followers/"
        
        params = {"count": 100, "search_surface": "follow_list_page"}
        if max_id:
            params["max_id"] = max_id
        
        start_time = time.time()
        response = self.session.get(url, headers=self.headers, params=params)
        request_time = time.time() - start_time
        
        return response, request_time

    def get_all_followers(self, user_id: str, max_followers: int = None, base_delay: float = 3.0) -> list:
        all_followers = []
        max_id = None
        page = 1
        current_delay = base_delay
        total_start_time = time.time()
        total_request_time = 0
        
        while True:
            Actor.log.info(f"Fetching page {page}...")
            
            response, request_time = self.get_followers(user_id, max_id)
            total_request_time += request_time
            
            Actor.log.info(f"Request time: {request_time:.2f}s | Status: {response.status_code}")
            
            # Handle rate limiting with retry
            if response.status_code == 401 or response.status_code == 429:
                Actor.log.warning(f"Rate limited. Waiting 20s before retry...")
                time.sleep(20)
                current_delay = 6.0
                Actor.log.info(f"Increased delay to {current_delay:.1f}s")
                
                response, request_time = self.get_followers(user_id, max_id)
                total_request_time += request_time
                
                if response.status_code != 200:
                    Actor.log.error(f"Retry failed: {response.status_code} - {response.text[:200]}")
                    break
            
            if response.status_code != 200:
                Actor.log.error(f"Error: {response.status_code} - {response.text[:200]}")
                break
            
            data = response.json()
            
            if "users" not in data:
                Actor.log.warning(f"No users in response")
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
            
            # Jitter: delay ± 30%
            jitter = current_delay * 0.3
            sleep_time = current_delay + random.uniform(-jitter, jitter)
            Actor.log.info(f"Sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        # Log timing summary
        total_time = time.time() - total_start_time
        Actor.log.info(f"=== TIMING SUMMARY ===")
        Actor.log.info(f"Total requests: {page}")
        Actor.log.info(f"Total request time: {total_request_time:.2f}s")
        Actor.log.info(f"Total execution time: {total_time:.2f}s")
        Actor.log.info(f"Avg request time: {total_request_time/page:.2f}s")
        Actor.log.info(f"======================")
            
        return all_followers


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        
        user_id = actor_input.get("user_id")
        authorization_token = actor_input.get("authorization_token", "")
        max_followers = actor_input.get("max_followers")
        delay = actor_input.get("delay", 3.0)
        webhook_url = actor_input.get("webhook_url")
        
        cookies = {
            "x-mid": actor_input.get("cookie_x_mid", ""),
            "ig-u-ds-user-id": actor_input.get("cookie_ds_user_id", ""),
            "ig-u-rur": actor_input.get("cookie_rur", ""),
        }
        
        Actor.log.info(f"user_id: {user_id}")
        Actor.log.info(f"authorization_token length: {len(authorization_token)}")
        Actor.log.info(f"max_followers: {max_followers}")
        Actor.log.info(f"delay: {delay}")
        
        if not user_id:
            raise ValueError("user_id is required")
        if not authorization_token:
            raise ValueError("authorization_token is required")
        
        Actor.log.info(f"Starting Instagram Followers Scraper for user_id: {user_id}")
        
        scraper = InstagramScraper(authorization_token, cookies)
        followers = scraper.get_all_followers(user_id, max_followers, delay)
        
        Actor.log.info(f"Scraped {len(followers)} followers total")
        
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
        
        await Actor.set_value("summary", {
            "user_id": user_id,
            "total_followers": len(followers),
            "scraped_at": datetime.now().isoformat(),
        })
        
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
