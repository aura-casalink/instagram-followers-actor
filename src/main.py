#!/usr/bin/env python3
"""
Instagram Followers Scraper using Playwright
"""

import asyncio
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
            Actor.log.error("Missing required inputs")
            await Actor.fail(status_message="Missing required inputs")
            return
        
        Actor.log.info(f"Starting scraper for @{username}")
        
        all_followers = []
        seen_pks = set()
        no_new_data_count = 0
        max_no_new_data = 15
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Cookies
            await context.add_cookies([
                {"name": "sessionid", "value": unquote(session_id), "domain": ".instagram.com", "path": "/", "secure": True, "httpOnly": True},
                {"name": "csrftoken", "value": csrf_token, "domain": ".instagram.com", "path": "/", "secure": True},
                {"name": "ds_user_id", "value": ds_user_id or session_id.split("%3A")[0], "domain": ".instagram.com", "path": "/", "secure": True},
            ])
            
            page = await context.new_page()
            
            # Log ALL responses to debug
            async def log_response(response):
                if "instagram.com/api" in response.url:
                    Actor.log.info(f"API Response: {response.status} - {response.url[:100]}")
            
            page.on("response", log_response)
            
            # Intercept followers API
            async def handle_followers(response):
                nonlocal no_new_data_count
                try:
                    if "/friendships/" in response.url and "followers" in response.url and response.status == 200:
                        Actor.log.info(f">>> FOLLOWERS API HIT: {response.url[:80]}")
                        data = await response.json()
                        users = data.get("users", [])
                        Actor.log.info(f">>> Got {len(users)} users in response")
                        
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
                            Actor.log.info(f"Added {new_count} followers (total: {len(all_followers)})")
                        else:
                            no_new_data_count += 1
                except Exception as e:
                    Actor.log.error(f"Error parsing response: {e}")
            
            page.on("response", handle_followers)
            
            # Navigate to profile first
            Actor.log.info(f"Loading profile page...")
            await page.goto(f"https://www.instagram.com/{username}/", wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(3000)
            
            # Screenshot to debug
            await page.screenshot(path="/tmp/debug1_profile.png")
            Actor.log.info(f"Current URL: {page.url}")
            
            # Check for login redirect
            if "login" in page.url:
                Actor.log.error("Redirected to login - session invalid")
                await Actor.fail(status_message="Session expired")
                return
            
            # Find and click followers count
            Actor.log.info("Looking for followers link...")
            
            # Try to find followers link with multiple strategies
            followers_clicked = False
            
            # Strategy 1: Find by href
            try:
                link = page.locator(f'a[href="/{username}/followers/"]')
                if await link.count() > 0:
                    Actor.log.info("Found followers link by href")
                    await link.first.click()
                    followers_clicked = True
            except Exception as e:
                Actor.log.info(f"Strategy 1 failed: {e}")
            
            # Strategy 2: Find by text content
            if not followers_clicked:
                try:
                    link = page.get_by_role("link", name="followers")
                    if await link.count() > 0:
                        Actor.log.info("Found followers link by role")
                        await link.first.click()
                        followers_clicked = True
                except Exception as e:
                    Actor.log.info(f"Strategy 2 failed: {e}")
            
            # Strategy 3: Direct navigation
            if not followers_clicked:
                Actor.log.info("Trying direct navigation to followers URL")
                await page.goto(f"https://www.instagram.com/{username}/followers/", wait_until="networkidle", timeout=60000)
            
            await page.wait_for_timeout(5000)
            await page.screenshot(path="/tmp/debug2_followers.png")
            Actor.log.info(f"After followers click URL: {page.url}")
            
            # Save screenshots to key-value store
            kvs = await Actor.open_key_value_store()
            with open("/tmp/debug1_profile.png", "rb") as f:
                await kvs.set_value("debug1_profile.png", f.read(), content_type="image/png")
            with open("/tmp/debug2_followers.png", "rb") as f:
                await kvs.set_value("debug2_followers.png", f.read(), content_type="image/png")
            Actor.log.info("Screenshots saved to key-value store")
            
            # Scroll loop
            Actor.log.info("Starting scroll loop...")
            scroll_count = 0
            
            while True:
                scroll_count += 1
                
                if max_followers and len(all_followers) >= max_followers:
                    Actor.log.info(f"Reached max: {max_followers}")
                    break
                
                if no_new_data_count >= max_no_new_data:
                    Actor.log.info("No new data, stopping")
                    break
                
                # Try to scroll the modal dialog
                await page.evaluate("""() => {
                    const dialog = document.querySelector('div[role="dialog"]');
                    if (dialog) {
                        const lists = dialog.querySelectorAll('div');
                        for (const el of lists) {
                            if (el.scrollHeight > el.clientHeight + 10) {
                                el.scrollTop = el.scrollHeight;
                            }
                        }
                    }
                    window.scrollTo(0, document.body.scrollHeight);
                }""")
                
                await page.wait_for_timeout(2000)
                
                if scroll_count % 5 == 0:
                    Actor.log.info(f"Scroll {scroll_count}: {len(all_followers)} followers")
                
                if scroll_count > 50:
                    Actor.log.info("Max scrolls reached")
                    break
            
            await browser.close()
        
        Actor.log.info(f"DONE: {len(all_followers)} followers")
        
        if all_followers:
            if max_followers:
                all_followers = all_followers[:max_followers]
            await Actor.push_data(all_followers)


if __name__ == "__main__":
    asyncio.run(main())
