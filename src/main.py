#!/usr/bin/env python3
"""
Instagram Mobile API Followers Scraper
Uses i.instagram.com with Bearer token (Android app simulation)
"""

import asyncio
import requests
import time
from apify import Actor


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        
        user_id = actor_input.get("user_id")
        authorization = actor_input.get("authorization")
        device_id = actor_input.get("device_id", "android-acd484febac47e6b")
        max_followers = actor_input.get("max_followers")
        delay = actor_input.get("delay", 2.0)
        
        if not user_id or not authorization:
            Actor.log.error("Missing required: user_id, authorization")
            await Actor.fail(status_message="Missing inputs")
            return
        
        # Ensure Bearer prefix
        if not authorization.startswith("Bearer "):
            authorization = f"Bearer {authorization}"
        
        Actor.log.info(f"Starting Mobile API scraper for user_id: {user_id}")
        Actor.log.info(f"Device ID: {device_id}")
        Actor.log.info(f"Max followers: {max_followers or 'unlimited'}")
        Actor.log.info(f"Delay: {delay}s")
        
        session = requests.Session()
        
        headers = {
            "User-Agent": "Instagram 330.0.0.40.92 Android (34/14; 420dpi; 1080x2400; Google/google; sdk_gphone64_arm64; emu64a; ranchu; en_US; 598323397)",
            "X-IG-App-ID": "567067343352427",
            "X-IG-Device-ID": device_id,
            "X-IG-Android-ID": device_id,
            "X-IG-Connection-Type": "WIFI",
            "X-IG-Capabilities": "3brTvx0=",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Host": "i.instagram.com",
            "Authorization": authorization,
        }
        
        session.headers.update(headers)
        
        all_followers = []
        max_id = None
        page = 0
        total_request_time = 0
        start_time = time.time()
        
        while True:
            page += 1
            
            params = {"count": 100, "search_surface": "follow_list_page"}
            if max_id:
                params["max_id"] = max_id
            
            url = f"https://i.instagram.com/api/v1/friendships/{user_id}/followers/"
            
            try:
                req_start = time.time()
                response = session.get(url, params=params, timeout=30)
                req_time = time.time() - req_start
                total_request_time += req_time
                
                Actor.log.info(f"Page {page}: {response.status_code} | {req_time:.2f}s")
                
                if response.status_code == 200:
                    data = response.json()
                    users = data.get("users", [])
                    
                    for user in users:
                        all_followers.append({
                            "pk": str(user.get("pk")),
                            "username": user.get("username"),
                            "full_name": user.get("full_name", ""),
                            "is_private": user.get("is_private", False),
                            "is_verified": user.get("is_verified", False),
                            "profile_pic_url": user.get("profile_pic_url", ""),
                        })
                    
                    Actor.log.info(f"  Got {len(users)} followers (total: {len(all_followers)})")
                    
                    max_id = data.get("next_max_id")
                    if not max_id:
                        Actor.log.info("Reached end of followers list")
                        break
                    
                    if max_followers and len(all_followers) >= max_followers:
                        Actor.log.info(f"Reached max: {max_followers}")
                        break
                
                elif response.status_code == 401:
                    error = response.json().get("message", "Unauthorized")
                    Actor.log.error(f"Auth error: {error}")
                    
                    if "wait" in error.lower() or "espera" in error.lower():
                        Actor.log.warning("Rate limited, waiting 30s...")
                        await asyncio.sleep(30)
                        continue
                    else:
                        await Actor.fail(status_message=f"Auth failed: {error}")
                        return
                
                elif response.status_code == 429:
                    Actor.log.warning("Rate limited (429), waiting 60s...")
                    await asyncio.sleep(60)
                    continue
                
                else:
                    Actor.log.error(f"Error: {response.status_code} - {response.text[:200]}")
                    break
                    
            except Exception as e:
                Actor.log.error(f"Exception: {e}")
                break
            
            await asyncio.sleep(delay)
        
        total_time = time.time() - start_time
        
        Actor.log.info("=" * 50)
        Actor.log.info("SCRAPING COMPLETE")
        Actor.log.info("=" * 50)
        Actor.log.info(f"Total followers: {len(all_followers)}")
        Actor.log.info(f"Total pages: {page}")
        Actor.log.info(f"Total time: {total_time:.1f}s")
        Actor.log.info(f"Request time: {total_request_time:.1f}s")
        Actor.log.info(f"Avg per page: {total_time/page:.2f}s")
        Actor.log.info(f"Followers/second: {len(all_followers)/total_time:.1f}")
        Actor.log.info("=" * 50)
        
        if all_followers:
            if max_followers:
                all_followers = all_followers[:max_followers]
            await Actor.push_data(all_followers)
            Actor.log.info(f"Pushed {len(all_followers)} to dataset")


if __name__ == "__main__":
    asyncio.run(main())
