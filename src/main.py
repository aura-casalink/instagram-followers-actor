#!/usr/bin/env python3
"""
Instagram Followers Scraper using Playwright
Intercepts API responses from a real browser session
"""

import asyncio
import json
from urllib.parse import unquote
from apify import Actor
from playwright.async_api import async_playwright


async def main():
    async with Actor:
        actor_input = await Actor.get_input() or {}
        
        username = actor_input.get("username", "").lstrip("@")
        session_id = actor_input.get("session_id")
        csrf_token = actor_input.get("csrf_token")
        ds_user_id = actor_input.get("ds_user_id", "")
        max_followers = actor_input.get("max_followers")
        
        if not username or not session_id or not csrf_token:
            Actor.log.error("Missing required inputs: username, session_id, csrf_token")
            await Actor.fail(status_message="Missing required inputs")
            return
        
        Actor.log.info(f"Starting Playwright scraper for @{username}")
        Actor.log.info(f"Max followers: {max_followers or 'unlimited'}")
        
        all_followers = []
        seen_pks = set()
        no_new_data_count = 0
        max_no_new_data = 15
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Set cookies
            cookies = [
                {"name": "sessionid", "value": unquote(session_id), "domain": ".instagram.com", "path": "/", "secure": True, "httpOnly": True},
                {"name": "csrftoken", "value": csrf_token, "domain": ".instagram.com", "path": "/", "secure": True},
                {"name": "ds_user_id", "value": ds_user_id or session_id.split("%3A")[0], "domain": ".instagram.com", "path": "/", "secure": True},
            ]
            await context.add_cookies(cookies)
            
            page = await context.new_page()
            
            # Intercept API responses
            async def handle_response(response):
                nonlocal no_new_data_count
                try:
                    if "/friendships/" in response.url and "/followers/" in response.url and response.status == 200:
                        data = await response.json()
                        users = data.get("users", [])
                        new_count = 0
                        for user in users:
                            pk = str(user.get("pk"))
                            if pk not in seen_pks:
                                seen_pks.add(pk)
                                all_followers.append({
                                    "pk": pk,
                                    "username": user.get("username"),
                                    "full_name": user.get("full_name"),
                                    "is_private": user.get("is_private"),
                                    "is_verified": user.get("is_verified"),
                                    "profile_pic_url": user.get("profile_pic_url"),
                                })
                                new_count += 1
                        if new_count > 0:
                            no_new_data_count = 0
                            Actor.log.info(f"Pulled {new_count} new followers (total: {len(all_followers)})")
                        else:
                            no_new_data_count += 1
                except:
                    pass
            
            page.on("response", handle_response)
            
            # Go directly to followers page
            Actor.log.info(f"Navigating to followers page...")
            await page.goto(f"https://www.instagram.com/{username}/followers/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)
            
            # Check if we got redirected to login
            if "login" in page.url:
                Actor.log.error("Session invalid - redirected to login")
                await Actor.fail(status_message="Session expired")
                return
            
            Actor.log.info("Starting to scroll and collect followers...")
            
            scroll_count = 0
            while True:
                scroll_count += 1
                
                if max_followers and len(all_followers) >= max_followers:
                    Actor.log.info(f"Reached max: {max_followers}")
                    break
                
                if no_new_data_count >= max_no_new_data:
                    Actor.log.info("No new data, assuming end reached")
                    break
                
                # Scroll using JavaScript function
                await page.evaluate("""() => {
                    const scrollable = document.querySelector('div[role="dialog"] div[style*="overflow"]') ||
                                      document.querySelector('div[role="dialog"]')?.querySelector('div > div > div') ||
                                      document.querySelector('div[class*="x1n2onr6"]');
                    if (scrollable) {
                        scrollable.scrollTop = scrollable.scrollHeight;
                    } else {
                        window.scrollTo(0, document.body.scrollHeight);
                    }
                }""")
                
                await page.wait_for_timeout(2000)
                
                if scroll_count % 10 == 0:
                    Actor.log.info(f"Scroll {scroll_count}: {len(all_followers)} followers")
            
            await browser.close()
        
        Actor.log.info("=" * 50)
        Actor.log.info(f"COMPLETE: {len(all_followers)} followers in {scroll_count} scrolls")
        Actor.log.info("=" * 50)
        
        if all_followers:
            if max_followers:
                all_followers = all_followers[:max_followers]
            await Actor.push_data(all_followers)
            Actor.log.info(f"Pushed {len(all_followers)} to dataset")


if __name__ == "__main__":
    asyncio.run(main())
