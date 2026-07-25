import requests
import re
import os
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# Directory
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

def get_all_slugs_from_page():
    """Get all channel slugs from the main page"""
    try:
        response = requests.get(TOKEN_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            # Look for channel slugs in the page
            slugs = re.findall(r'data-channel="([a-zA-Z0-9_-]+)"', response.text)
            return list(set(slugs))  # Remove duplicates
        return []
    except:
        return []

def discover_working_channels(token, slug_list):
    """Try all possible slugs with token"""
    working = {}
    
    # Test slugs from config + discovered slugs
    test_slugs = list(set(slug_list))
    
    # Add known slugs from your example
    test_slugs.extend(['tmb_az_app', 'tmbaz', 'tmbtr'])
    
    print(f"🔍 Testing {len(test_slugs)} slugs...")
    
    for slug in test_slugs:
        # Try different URL patterns
        patterns = [
            f"https://str.yodacdn.net/{slug}/video.m3u8?token={token}",
            f"https://str.yodacdn.net/{slug}/index.m3u8?token={token}",
            f"https://str1.yodacdn.net/{slug}/video.m3u8?token={token}",
        ]
        
        for url in patterns:
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    working[slug] = response.text
                    print(f"   ✅ {slug} - Working")
                    break
            except:
                continue
        
        if slug not in working:
            print(f"   ❌ {slug} - Failed")
    
    return working

def save_results(working_channels, token, timestamp):
    """Save results"""
    for slug, content in working_channels.items():
        # Fix relative paths
        lines = content.split("\n")
        fixed_lines = []
        base_url = f"https://str.yodacdn.net/{slug}/"
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("http"):
                track_url = base_url + line
                if '?' in track_url:
                    track_url = f"{track_url}&token={token}"
                else:
                    track_url = f"{track_url}?token={token}"
                fixed_lines.append(track_url)
            else:
                fixed_lines.append(line)
        
        filename = os.path.join(output_dir, f"{slug}.m3u8")
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(fixed_lines))
    
    # Master playlist
    master_file = os.path.join(output_dir, f"master_{timestamp}.m3u8")
    with open(master_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for slug, content in working_channels.items():
            f.write(f'\n#EXTINF:-1,{slug.upper()}\n')
            match = re.search(r'https://str[0-9]*\.yodacdn\.net/[^/]+/[^\n]+\.m3u8', content)
            if match:
                f.write(match.group(0) + "\n")
    
    print(f"\n✅ Found {len(working_channels)} working channels")
    print(f"   Slugs: {', '.join(working_channels.keys())}")

def main():
    print("🚀 Starting Yoda Channel Discovery...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Get token
    token = get_token()
    if not token:
        print("❌ Failed to get token")
        exit(1)
    print(f"✅ Token: {token[:10]}...")
    
    # Get slugs from page
    slugs = get_all_slugs_from_page()
    print(f"📺 Found {len(slugs)} slugs in page: {slugs}")
    
    # Add manual slugs
    manual_slugs = [
        'azertv', 'xazar', 'ictimaitv', 'bakutv', 'idmantele',
        'biznestv', 'ntv', 'real', 'qafkaz', 'atv', 'arb24',
        'apatv', 'haberglobal', 'tmbtr', 'tmbaz', 'arb',
        'start', 'kanal35', 'eltv', 'arbgunesh', 'cbc',
        'medeniyyettele', 'space', 'tmb', 'showplus',
        'mtvaz', 'shtv', 'vip', 'tmb_az_app'
    ]
    
    all_slugs = list(set(slugs + manual_slugs))
    
    # Discover working channels
    working = discover_working_channels(token, all_slugs)
    
    # Save
    if working:
        save_results(working, token, timestamp)
    else:
        print("❌ No working channels found")

if __name__ == "__main__":
    main()
