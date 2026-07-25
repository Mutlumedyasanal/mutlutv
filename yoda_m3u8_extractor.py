import requests
import re
import os
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# Directory to save output files
output_dir = "links/yoda"
os.makedirs(output_dir, exist_ok=True)

# Headers
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Referer": "https://yoda.az/",
    "Origin": "https://yoda.az/",
}

# URLs
TOKEN_URL = "https://yodaplayer.yodacdn.net/"
CHANNEL_CONFIG_URL = "https://yoda.az/tv.channel.config.js"

def get_channel_config():
    """Fetch channel configuration from yoda.az using regex"""
    print("📡 Fetching channel configuration...")
    try:
        response = requests.get(CHANNEL_CONFIG_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            js_content = response.text
            
            channels = []
            
            # Pattern to match each channel object
            pattern = r'\{[^{}]*channelID:\s*"([^"]+)"[^{}]*channelName:\s*"([^"]+)"[^{}]*channelSource:\s*"([^"]+)"[^{}]*\}'
            
            matches = re.findall(pattern, js_content, re.DOTALL)
            
            for match in matches:
                channel_id = match[0]
                channel_name = match[1]
                source_url = match[2]
                
                # Extract slug from URL
                slug_match = re.search(r'https?://str[0-9]*\.yodacdn\.net/([^/]+)/', source_url)
                if slug_match:
                    slug = slug_match.group(1)
                else:
                    slug = channel_id
                
                channels.append({
                    "id": channel_id,
                    "name": channel_name,
                    "slug": slug,
                    "source": source_url
                })
            
            print(f"✅ Found {len(channels)} channels in config")
            return channels
        else:
            print(f"❌ Failed to fetch config: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error fetching channel config: {e}")
        return []

def get_token_via_selenium():
    """Get token using Selenium"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    chrome_paths = [
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium"
    ]
    
    for chrome_path in chrome_paths:
        if os.path.exists(chrome_path):
            chrome_options.binary_location = chrome_path
            break
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get(TOKEN_URL)
        driver.implicitly_wait(10)
        
        page_source = driver.page_source
        token_match = re.search(r'data-token="([a-zA-Z0-9_-]+)"', page_source)
        driver.quit()
        
        if token_match:
            return token_match.group(1)
        else:
            print("❌ Token not found using Selenium.")
            return None
    except Exception as e:
        print(f"❌ Error fetching token via Selenium: {e}")
        try:
            driver.quit()
        except:
            pass
        return None

def get_token_via_requests():
    """Fallback: Get token using requests"""
    print("🔄 Trying to fetch token via standard request...")
    try:
        response = requests.get(TOKEN_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            site_content = response.text
            match = re.search(r'data-token="([a-zA-Z0-9_-]+)"', site_content)
            if match:
                return match.group(1)
        return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def process_channel(channel, token):
    """Process a single channel - extract all track URLs"""
    slug = channel['slug']
    name = channel['name']
    channel_id = channel['id']
    source_url = channel['source']
    
    # Add token to URL
    if '?' in source_url:
        m3u8_url = f"{source_url}&token={token}"
    else:
        m3u8_url = f"{source_url}?token={token}"
    
    print(f"📡 Processing: {name} ({slug})")
    
    try:
        content_response = requests.get(m3u8_url, headers=headers, timeout=10)
        
        if content_response.status_code == 200:
            content = content_response.text
            lines = content.split("\n")
            modified_lines = []
            
            # Base URL for relative paths
            base_url = re.sub(r'/[^/]+$', '/', source_url)
            
            for line in lines:
                line = line.strip()
                
                # If line is a relative path (not starting with http or #)
                if line and not line.startswith("#") and not line.startswith("http"):
                    # Fix: add token to the track URL too
                    track_url = base_url + line
                    if '?' in track_url:
                        track_url = f"{track_url}&token={token}"
                    else:
                        track_url = f"{track_url}?token={token}"
                    modified_lines.append(track_url)
                else:
                    modified_lines.append(line)
            
            return "\n".join(modified_lines)
        else:
            print(f"   ⚠️ Failed: Status {content_response.status_code}")
            return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def save_results(results, channels, timestamp):
    """Save results to files"""
    # Save individual channel files
    for channel in channels:
        channel_id = channel['id']
        content = results.get(channel_id)
        if content:
            filename = os.path.join(output_dir, f"{channel_id}.m3u8")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
    
    # Save master playlist
    master_file = os.path.join(output_dir, f"master_{timestamp}.m3u8")
    with open(master_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for channel in channels:
            channel_id = channel['id']
            content = results.get(channel_id)
            if content:
                name = channel['name']
                f.write(f'\n#EXTINF:-1,{name}\n')
                # Extract first track URL (any line starting with http)
                match = re.search(r'https://str[0-9]*\.yodacdn\.net/[^/]+/[^\n]+\.m3u8', content)
                if match:
                    f.write(match.group(0) + "\n")
    
    # Save metadata
    meta_file = os.path.join(output_dir, f"metadata_{timestamp}.json")
    with open(meta_file, "w", encoding="utf-8") as f:
        working = [ch for ch in channels if results.get(ch['id'])]
        failed = [ch for ch in channels if not results.get(ch['id'])]
        json.dump({
            "timestamp": timestamp,
            "total_channels": len(channels),
            "working_count": len(working),
            "working_channels": [ch['name'] for ch in working],
            "failed_channels": [ch['name'] for ch in failed]
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Results saved to {output_dir}/")
    print(f"   - Working: {len(working)}/{len(channels)} channels")
    if failed:
        print(f"   - Failed: {len(failed)} channels")

def main():
    """Main function"""
    print("🚀 Starting Yoda M3U8 Extractor...")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    # Get channel config first
    channels = get_channel_config()
    if not channels:
        print("❌ Failed to get channel configuration. Exiting.")
        exit(1)
    
    print(f"📺 Found {len(channels)} channels")
    print("-" * 50)
    
    # Get token
    token = get_token_via_selenium()
    if not token:
        token = get_token_via_requests()
    
    if not token:
        print("❌ Failed to retrieve token. Exiting.")
        exit(1)
    
    print(f"✅ Token retrieved: {token[:10]}...")
    print("-" * 50)
    
    # Process all channels
    results = {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for i, channel in enumerate(channels, 1):
        print(f"[{i}/{len(channels)}] ", end="")
        content = process_channel(channel, token)
        results[channel['id']] = content
        if content:
            print(f"   ✅ OK")
        else:
            print(f"   ❌ FAILED")
    
    # Save results
    save_results(results, channels, timestamp)
    print("\n✅ Process completed successfully!")

if __name__ == "__main__":
    main()
