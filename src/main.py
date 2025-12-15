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
        
        # Input parameters
        username = actor_input.get("username")
        session_id = actor_input.get("session_id")
        csrf_token = actor_input.get("csrf_token")
        ds_user_id = actor_input.get("ds_user_id", "")
        max_followers = actor_input.get("max_followers")
        
        if not username:
            Actor.log.error("Missing required input: username")
            await Actor.fail(status_message="Missing username")
            return
        
        if not session_id or not csrf_token:
            Actor.log.error("Missing required cookies: session_id and csrf_token")
            await Actor.fail(status_message="Missing session cookies")
            return
        
        # Remove @ if present
        username = username.lstrip("@")
        
        Actor.log.info(f"Starting Playwright scraper for @{username}")
        Actor.log.info(f"Max followers: {max_followers or 'unlimited'}")
        
        all_followers = []
        seen_pks = set()
        scroll_count = 0
        no_new_data_count = 0
        max_no_new_data = 10  # Stop after 10 scrolls with no new data
        
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Set cookies
            cookies = [
                {
                    "name": "sessionid",
                    "value": unquote(session_id),
                    "domain": ".instagram.com",
                    "path": "/",
                    "secure": True,
                    "httpOnly": True,
                },
                {
                    "name": "csrftoken",
                    "value": csrf_token,
                    "domain": ".instagram.com",
                    "path": "/",
                    "secure": True,
                },
                {
                    "name": "ds_user_id",
                    "value": ds_user_id or session_id.split("%3A")[0],
                    "domain": ".instagram.com",
                    "path": "/",
                    "secure": True,
                },
            ]
            
            await context.add_cookies(cookies)
            
            page = await context.new_page()
            
            # Intercept API responses
            async def handle_response(response):
                nonlocal no_new_data_count
                
                try:
                    url = response.url
                    if "/friendships/" in url and "/followers/" in url and response.status == 200:
                        data = await response.json()
                        users = data.get("users", [])
                        
                        new_count = 0
                        for user in users:
                            pk = str(user.get("pk"))
                            if pk not in seen_pks:
                                seen_pks.add(pk)
                                follower = {
                                    "pk": pk,
                                    "username": user.get("username"),
                                    "full_name": user.get("full_name"),
                                    "is_private": user.get("is_private"),
                                    "is_verified": user.get("is_verified"),
                                    "profile_pic_url": user.get("profile_pic_url"),
                                }
                                all_followers.append(follower)
                                new_count += 1
                        
                        if new_count > 0:
                            no_new_data_count = 0
                            Actor.log.info(f"Pulled {new_count} new followers (total: {len(all_followers)})")
                        else:
                            no_new_data_count += 1
                            
                except Exception as e:
                    pass  # Ignore parsing errors for non-JSON responses
            
            page.on("response", handle_response)
            
            # Navigate to profile
            Actor.log.info(f"Navigating to @{username} profile...")
            
            try:
                await page.goto(f"https://www.instagram.com/{username}/", wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)
            except Exception as e:
                Actor.log.error(f"Failed to load profile: {e}")
                await Actor.fail(status_message=f"Failed to load profile: {e}")
                return
            
            # Click on followers link
            Actor.log.info("Opening followers dialog...")
            
            try:
                # Try different selectors for followers link
                followers_selector = f'a[href="/{username}/followers/"]'
                await page.wait_for_selector(followers_selector, timeout=10000)
                await page.click(followers_selector)
                await page.wait_for_timeout(3000)
            except Exception as e:
                Actor.log.error(f"Could not find followers link: {e}")
                # Try alternative: direct navigation
                try:
                    await page.goto(f"https://www.instagram.com/{username}/followers/", wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(3000)
                except Exception as e2:
                    Actor.log.error(f"Direct navigation also failed: {e2}")
                    await Actor.fail(status_message="Could not open followers")
                    return
            
            # Find the scrollable dialog
            Actor.log.info("Starting to scroll and collect followers...")
            
            # Wait for followers list to appear
            await page.wait_for_timeout(2000)
            
            # Scroll loop
            while True:
                scroll_count += 1
                
                # Check if we've reached max
                if max_followers and len(all_followers) >= max_followers:
                    Actor.log.info(f"Reached max followers limit: {max_followers}")
                    break
                
                # Check if no new data for too long
                if no_new_data_count >= max_no_new_data:
                    Actor.log.info(f"No new data after {max_no_new_data} scrolls, assuming end reached")
                    break
                
                # Scroll the followers dialog
                try:
                    # Find the scrollable container (the dialog with followers list)
                    scroll_script = """
                        const dialog = document.querySelector('div[role="dialog"]');
                        if (dialog) {
                            const scrollable = dialog.querySelector('div[style*="overflow"]') || 
                                              dialog.querySelector('div[class*="scroll"]') ||
                                              dialog.querySelectorAll('div')[5];
                            if (scrollable) {
                                scrollable.scrollTop = scrollable.scrollHeight;
                                return true;
                            }
                        }
                        // Fallback: try to scroll any visible scrollable element
                        const scrollables = document.querySelectorAll('[style*="overflow: auto"], [style*="overflow-y: auto"]');
                        for (const el of scrollables) {
                            if (el.scrollHeight > el.clientHeight) {
                                el.scrollTop = el.scrollHeight;
                                return true;
                            }
                        }
                        return false;
                    """
                    
                    scrolled = await page.evaluate(scroll_script)
                    
                    if not scrolled:
                        # Alternative: keyboard scroll
                        await page.keyboard.press("End")
                    
                except Exception as e:
                    Actor.log.warning(f"Scroll error: {e}")
                
                # Wait for new content to load
                await page.wait_for_timeout(2000)
                
                # Log progress every 10 scrolls
                if scroll_count % 10 == 0:
                    Actor.log.info(f"Scroll {scroll_count}: {len(all_followers)} followers collected")
            
            await browser.close()
        
        # Results
        Actor.log.info("=" * 50)
        Actor.log.info("SCRAPING COMPLETE")
        Actor.log.info("=" * 50)
        Actor.log.info(f"Total followers: {len(all_followers)}")
        Actor.log.info(f"Total scrolls: {scroll_count}")
        
        if all_followers:
            # Trim to max if needed
            if max_followers and len(all_followers) > max_followers:
                all_followers = all_followers[:max_followers]
            
            await Actor.push_data(all_followers)
            Actor.log.info(f"Pushed {len(all_followers)} followers to dataset")
        else:
            Actor.log.warning("No followers collected")


if __name__ == "__main__":
    asyncio.run(main())
