#!/usr/bin/env python3
"""
Instagram Web API Followers Scraper - Apify Actor
Uses www.instagram.com/api/v1/ endpoint with browser session cookies
"""

import asyncio
import json
import time
import random
import requests
from apify import Actor


async def main():
    async with Actor:
        # Get input
        actor_input = await Actor.get_input() or {}
        
        # Required parameters
        user_id = actor_input.get("user_id")
        session_id = actor_input.get("session_id")
        csrf_token = actor_input.get("csrf_token")
        
        # Optional parameters with defaults
        ds_user_id = actor_input.get("ds_user_id", user_id)
        ig_did = actor_input.get("ig_did", "")
        mid = actor_input.get("mid", "")
        www_claim = actor_input.get("www_claim", "0")
        
        max_followers = actor_input.get("max_followers")  # None = unlimited
        delay = actor_input.get("delay", 3.0)
        
        # Validate required inputs
        if not user_id:
            Actor.log.error("Missing required input: user_id")
            await Actor.fail(status_message="Missing user_id")
            return
        
        if not session_id:
            Actor.log.error("Missing required input: session_id")
            await Actor.fail(status_message="Missing session_id")
            return
            
        if not csrf_token:
            Actor.log.error("Missing required input: csrf_token")
            await Actor.fail(status_message="Missing csrf_token")
            return
        
        Actor.log.info(f"Starting Instagram Web API Followers Scraper")
        Actor.log.info(f"Target user_id: {user_id}")
        Actor.log.info(f"Max followers: {max_followers or 'unlimited'}")
        Actor.log.info(f"Delay: {delay}s")
        
        # Setup session
        session = requests.Session()
        
        headers = {
            "Accept": "*/*",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": f"https://www.instagram.com/",
            "X-CSRFToken": csrf_token,
            "X-IG-App-ID": "936619743392459",
            "X-IG-WWW-Claim": www_claim,
            "X-ASBD-ID": "359341",
            "X-Requested-With": "XMLHttpRequest",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
        }
        
        cookies = {
            "sessionid": session_id,
            "csrftoken": csrf_token,
            "ds_user_id": ds_user_id,
        }
        
        # Add optional cookies if provided
        if ig_did:
            cookies["ig_did"] = ig_did
        if mid:
            cookies["mid"] = mid
        
        session.headers.update(headers)
        session.cookies.update(cookies)
        
        # Scraping loop
        all_followers = []
        max_id = None
        page = 0
        total_request_time = 0
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while True:
            page += 1
            
            # Build URL
            params = {
                "count": 50,  # Server returns max 25, but we ask for 50
                "search_surface": "follow_list_page",
            }
            
            if max_id:
                params["max_id"] = max_id
            
            url = f"https://www.instagram.com/api/v1/friendships/{user_id}/followers/"
            
            try:
                start_time = time.time()
                response = session.get(url, params=params, timeout=30)
                request_time = time.time() - start_time
                total_request_time += request_time
                
                Actor.log.info(f"Page {page}: Status {response.status_code} | Time: {request_time:.2f}s")
                
                if response.status_code == 200:
                    consecutive_errors = 0
                    data = response.json()
                    
                    users = data.get("users", [])
                    next_max_id = data.get("next_max_id")
                    
                    # Process users
                    for user in users:
                        follower = {
                            "pk": str(user.get("pk")),
                            "username": user.get("username"),
                            "full_name": user.get("full_name"),
                            "is_private": user.get("is_private"),
                            "is_verified": user.get("is_verified"),
                            "profile_pic_url": user.get("profile_pic_url"),
                        }
                        all_followers.append(follower)
                    
                    Actor.log.info(f"  Got {len(users)} followers (total: {len(all_followers)})")
                    
                    # Check pagination
                    if not next_max_id:
                        Actor.log.info("Reached end of followers list")
                        break
                    
                    max_id = next_max_id
                    
                    # Check max limit
                    if max_followers and len(all_followers) >= max_followers:
                        Actor.log.info(f"Reached max limit of {max_followers}")
                        break
                
                elif response.status_code == 401:
                    error_msg = response.json().get("message", "Unauthorized")
                    Actor.log.error(f"Authentication error: {error_msg}")
                    
                    # Check if it's a temporary rate limit or permanent auth failure
                    if "wait" in error_msg.lower():
                        Actor.log.warning("Rate limited. Waiting 60s before retry...")
                        await asyncio.sleep(60)
                        continue
                    else:
                        await Actor.fail(status_message=f"Auth failed: {error_msg}")
                        return
                
                elif response.status_code == 429:
                    Actor.log.warning("Rate limited (429). Waiting 60s...")
                    await asyncio.sleep(60)
                    continue
                
                else:
                    consecutive_errors += 1
                    Actor.log.error(f"Error {response.status_code}: {response.text[:200]}")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        Actor.log.error(f"Too many consecutive errors ({consecutive_errors}). Stopping.")
                        break
                    
                    await asyncio.sleep(10)
                    continue
                    
            except requests.exceptions.RequestException as e:
                consecutive_errors += 1
                Actor.log.error(f"Request exception: {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    Actor.log.error(f"Too many consecutive errors. Stopping.")
                    break
                
                await asyncio.sleep(10)
                continue
            
            # Delay with jitter
            jitter = delay * 0.2
            sleep_time = delay + random.uniform(-jitter, jitter)
            await asyncio.sleep(sleep_time)
        
        # Log summary
        Actor.log.info("=" * 50)
        Actor.log.info("SCRAPING COMPLETE")
        Actor.log.info("=" * 50)
        Actor.log.info(f"Total followers: {len(all_followers)}")
        Actor.log.info(f"Total pages: {page}")
        Actor.log.info(f"Total request time: {total_request_time:.2f}s")
        if page > 0:
            Actor.log.info(f"Avg request time: {total_request_time/page:.2f}s")
        
        # Push results to dataset
        if all_followers:
            await Actor.push_data(all_followers)
            Actor.log.info(f"Pushed {len(all_followers)} followers to dataset")
        else:
            Actor.log.warning("No followers scraped")


if __name__ == "__main__":
    asyncio.run(main())
