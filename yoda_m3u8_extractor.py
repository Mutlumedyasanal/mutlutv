import requests
import re
import os
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

output_dir = "links/yoda"
os.makedirs(output_dir, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Referer": "https://yoda.az/",
    "Origin": "https://yoda.az/",
}

TOKEN_URL = "https://yodaplayer.yodacdn.net/"
CHANNEL_CONFIG_URL = "https://yoda.az/tv.channel.config.js"

def get_token():
    """Get token"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
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
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_channel_config():
    """Get ALL channels from config with CORRECT slugs"""
    print("📡 Fetching channel config...")
    try:
        response = requests.get(CHANNEL_CONFIG_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            js_content = response.text
            
            # Extract all channel objects
            channels = []
            pattern = r'\{[^{}]*channelID:\s*"([^"]+)"[^{}]*channelName:\s*"([^"]+)"[^{}]*channelSource:\s*"([^"]+)"[^{}]*\}'
            matches = re.findall(pattern, js_content, re.DOTALL)
            
            for match in matches:
                channel_id = match[0]
                channel_name = match[1]
                source_url = match[2]
                
                # Extract the CORRECT slug from the URL
                # https://str.yodacdn.net/xazar/video.m3u8 -> xazar
                # https://str.yodacdn.net/ictimaitv/video.m3u8 -> ictimaitv
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
            
            print(f"✅ Found {len(channels)} channels")
            return channels
        else:
            print(f"❌ Failed: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def process_channel(channel, token):
    """Process channel with correct slug"""
    slug = channel['slug']
    name = channel['name']
    source_url = channel['source']
    
    # Use the slug from URL, NOT channelID
    # Try different URL patterns
    patterns = [
        f"https://str.yodacdn.net/{slug}/video.m3u8?token={token}",
        f"https://str.yodacdn.net/{slug}/index.m3u8?token={token}",
        f"https://str1.yodacdn.net/{slug}/video.m3u8?token={token}",
    ]
    
    print(f"📡 {name} ({slug})", end=" ")
    
    for url in patterns:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                content = response.text
                lines = content.split("\n")
                modified = []
                base_url = f"https://str.yodacdn.net/{slug}/"
                
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("http"):
                        track_url = base_url + line
                        if '?' in track_url:
                            track_url = f"{track_url}&token={token}"
                        else:
                            track_url = f"{track_url}?token={token}"
                        modified.append(track_url)
                    else:
                        modified.append(line)
                
                print("✅ OK")
                return "\n".join(modified)
        except:
            continue
    
    print("❌ FAILED")
    return None

def save_results(results, channels, timestamp):
    """Save results"""
    # Individual files
    for channel in channels:
        channel_id = channel['id']
        content = results.get(channel_id)
        if content:
            filename = os.path.join(output_dir, f"{channel_id}.m3u8")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
    
    # Master playlist - ALL working channels
    master_file = os.path.join(output_dir, f"master_{timestamp}.m3u8")
    with open(master_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for channel in channels:
            channel_id = channel['id']
            content = results.get(channel_id)
            if content:
                name = channel['name']
                f.write(f'\n#EXTINF:-1,{name}\n')
                match = re.search(r'https://str[0-9]*\.yodacdn\.net/[^/]+/[^\n]+\.m3u8', content)
                if match:
                    f.write(match.group(0) + "\n")
    
    # Metadata
    working = [ch for ch in channels if results.get(ch['id'])]
    failed = [ch for ch in channels if not results.get(ch['id'])]
    
    meta_file = os.path.join(output_dir, f"metadata_{timestamp}.json")
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "total_channels": len(channels),
            "working_count": len(working),
            "working_channels": [{
                "name": ch['name'],
                "slug": ch['slug'],
                "id": ch['id']
            } for ch in working],
            "failed_channels": [{
                "name": ch['name'],
                "slug": ch['slug'],
                "id": ch['id']
            } for ch in failed]
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Results saved!")
    print(f"   Working: {len(working)}/{len(channels)}")
    if working:
        print("   Working channels:")
        for ch in working:
            print(f"     ✅ {ch['name']} (slug: {ch['slug']})")
    if failed:
        print("   Failed channels:")
        for ch in failed:
            print(f"     ❌ {ch['name']} (slug: {ch['slug']})")

def main():
    print("🚀 Starting Yoda M3U8 Extractor...")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    # Get channels with correct slugs
    channels = get_channel_config()
    if not channels:
        exit(1)
    
    # Get token
    token = get_token()
    if not token:
        print("❌ Failed to get token")
        exit(1)
    print(f"✅ Token: {token[:10]}...")
    print("-" * 50)
    
    # Process ALL channels
    results = {}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for channel in channels:
        content = process_channel(channel, token)
        results[channel['id']] = content
    
    # Save
    save_results(results, channels, timestamp)

if __name__ == "__main__":
    main()
