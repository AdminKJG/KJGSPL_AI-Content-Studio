import os
import time
import base64
import logging
from playwright.sync_api import sync_playwright, TimeoutError

class VideoFXClient:
    """Client for generating videos using Google VideoFX via browser automation."""
    
    def __init__(self, user_data_dir: str):
        self.user_data_dir = user_data_dir
        self.url = "https://flow.google.com/"

    def login_if_needed(self):
        """Open Google Flow in a persistent Chrome profile for interactive login.

        Authentication is confirmed by reaching a Flow project, NOT by finding an
        arbitrary textbox on Google's landing page. Never log passwords or cookies.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=False,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"]
            )
            try:
                # A persistent context already has a default tab. Reuse it.
                page = browser.pages[0] if browser.pages else browser.new_page()
                page.goto(self.url, wait_until="domcontentloaded", timeout=60000)
                logging.info("Google Flow opened. Sign in normally and open a project.")
                logging.info("Waiting up to 10 minutes for a Flow project URL; do not close this window.")
                deadline = time.monotonic() + 600
                while time.monotonic() < deadline:
                    for tab in browser.pages:
                        if tab.url.startswith("https://flow.google.com/project/"):
                            logging.info("Google Flow project reached; local browser profile retained.")
                            return
                    time.sleep(2)
                raise RuntimeError(
                    "Google Flow project not reached within 10 minutes. "
                    "Sign in and open New project in the automation Chrome window, then retry."
                )
            finally:
                browser.close()

    def generate_video(self, prompt: str, output_path: str, on_frame_callback=None, stop_event=None):
        """Generates a video by automating the VideoFX UI and downloads it to output_path."""
        logging.info(f"Generating video with Google VideoFX (Browser Automation): '{prompt}'")
        
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=False,
                channel="chrome",
                args=["--disable-blink-features=AutomationControlled"],
                ignore_default_args=["--enable-automation"]
            )
            page = browser.new_page()
            
            # Intercept downloads
            def handle_download(download):
                logging.info("Download intercepted! Saving video...")
                download.save_as(output_path)
            
            page.on("download", handle_download)
            
            try:
                page.goto(self.url, wait_until="domcontentloaded")
                if page.url.startswith("https://flow.google.com"):
                    raise RuntimeError(
                        "Google Flow is accessible, but this legacy VideoFX automation "
                        "does not support the current project editor. The login connection "
                        "is separate from video generation. Do not retry paid generations "
                        "until a supported Flow integration is implemented."
                    )
                
                # 1. Enter the prompt
                # Use a more robust selector to avoid matching hidden recaptcha textareas
                prompt_locator = page.locator('textarea:not(.g-recaptcha-response), [contenteditable="true"], [role="textbox"], input[type="text"]').locator("visible=true").first
                prompt_locator.wait_for(timeout=30000)
                
                # Sometimes the input has placeholder text we need to clear or overwrite
                prompt_locator.fill(prompt)
                time.sleep(1)
                
                # 2. Click "Generate"
                # The generate button might be a button with text "Generate" or an icon
                # We will look for a button containing the word Generate (case insensitive)
                generate_button = page.locator('button:has-text("Generate"), button[aria-label="Generate"], button[title="Generate"]').first
                generate_button.click()
                
                logging.info("Generation started. Waiting for completion (this can take several minutes)...")
                
                # 3. Wait for the video generation to complete
                # VideoFX shows a progress bar or spinner. When it's done, a video element is usually present and playing
                # We wait for a video element that was recently added or for the download button.
                # Since the exact DOM is tricky, we can wait for the download button.
                # Download button is usually 'button:has-text("Download")' or has a download icon.
                # If we can't find a download button, we can extract the video src.
                
                # Let's wait for a download button or a video element
                # Video generation on Veo usually takes 1-2 minutes.
                download_btn_selector = 'button:has-text("Download"), button[aria-label*="Download"], a[download]'
                
                try:
                    start_time = time.time()
                    download_found = False
                    
                    while time.time() - start_time < 300: # Wait up to 5 minutes
                        if stop_event and stop_event.is_set():
                            raise InterruptedError("VideoFX generation was cancelled by the user.")
                            
                        if on_frame_callback:
                            try:
                                screenshot_bytes = page.screenshot(type="jpeg", quality=40)
                                b64_str = base64.b64encode(screenshot_bytes).decode("utf-8")
                                on_frame_callback(b64_str)
                            except Exception:
                                pass
                        
                        try:
                            page.wait_for_selector(download_btn_selector, timeout=1000)
                            download_found = True
                            break
                        except TimeoutError:
                            pass
                    
                    if not download_found:
                        raise TimeoutError("Download button not found after 5 minutes.")
                        
                    logging.info("Download button found, initiating download...")
                    
                    with page.expect_download(timeout=60000) as download_info:
                        page.locator(download_btn_selector).first.click()
                    
                    download_info.value.save_as(output_path)
                    logging.info(f"Video saved to {output_path}")
                    
                except TimeoutError:
                    logging.warning("Download button not found. Trying to extract video source directly...")
                    # Fallback: look for video tag
                    page.wait_for_selector("video", timeout=30000)
                    video_element = page.locator("video").first
                    video_url = video_element.get_attribute("src")
                    
                    if video_url:
                        logging.info(f"Video source found: {video_url[:50]}...")
                        # If it's a blob, we have to evaluate JS to download it
                        if video_url.startswith("blob:"):
                            script = """
                            async () => {
                                const video = document.querySelector('video');
                                const response = await fetch(video.src);
                                const blob = await response.blob();
                                return new Promise(resolve => {
                                    const reader = new FileReader();
                                    reader.onloadend = () => resolve(reader.result);
                                    reader.readAsDataURL(blob);
                                });
                            }
                            """
                            data_url = page.evaluate(script)
                            import urllib.request
                            import base64
                            response = urllib.request.urlopen(data_url)
                            with open(output_path, 'wb') as f:
                                f.write(response.file.read())
                            logging.info(f"Video saved to {output_path} via Blob extraction.")
                        else:
                            import requests
                            response = requests.get(video_url)
                            with open(output_path, 'wb') as f:
                                f.write(response.content)
                            logging.info(f"Video saved to {output_path} via standard URL.")
                    else:
                        raise RuntimeError("Could not find video element or download button.")
                
            except Exception as e:
                logging.error(f"VideoFX generation failed: {e}")
                # Save screenshot for debugging
                debug_path = output_path.replace(".mp4", "_debug_error.png")
                page.screenshot(path=debug_path)
                logging.info(f"Saved debug screenshot to {debug_path}")
                raise e
            finally:
                browser.close()

