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

# Headers for fallback request
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Referer": "https://yodaplayer.yodacdn.net/",
    "Origin": "https://yodaplayer.yodacdn.net/",
}

# URL to fetch tokens dynamically
url = "https://yodaplayer.yodacdn.net/"

# Channel list
names = [
    "aztv", "xazar", "arb24", "ntv", "apatv", "bakutv", "atv", 
    "haberglobal", "real", "tmbtr", "tmbaz", "arb", "start", 
    "ictimai", "kanal35", "idman", "gunaztv", "eltv", "qafkaz", 
    "arbgunesh", "cbc", "medeniyyet", "space", "tmb", "agrotv", 
    "showplus", "mtvaz", "shtv", "vip"
]

def get_token_via_selenium():
    """Get token using Selenium with Chrome in headless mode"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Chrome path'leri dene
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
        driver.get(url)
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
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            site_content = response.text
            match = re.search(r'data-token="([a-zA-Z0-9_-]+)"', site_content)
            if match:
                return match.group(1)
        return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def process_channel(name, token):
    """Process a single channel and return its M3U8 content"""
    m3u8_url = f"https://str.yodacdn.net/{name}/video.m3u8?token={token}"
    print(f"📡 Processing: {name}")
    
    try:
        content_response = requests.get(m3u8_url, headers=headers, timeout=10)
        
        if content_response.status_code == 200:
            content = content_response.text
            lines = content.split("\n")
            modified_content = []
            
            for line in lines:
                line = line.strip()
                if line.startswith("tracks"):
                    full_url = f"https://str.yodacdn.net/{name}/" + line
                    modified_content.append(full_url)
                else:
                    modified_content.append(line)
            
            return "\n".join(modified_content)
        else:
            print(f"⚠️ Failed to fetch m3u8 for {name} (Status: {content_response.status_code})")
            return None
    except Exception as e:
        print(f"❌ Error processing {name}: {e}")
        return None

def save_results(results, token):
    """Save results to files"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save individual channel files
    for name, content in results.items():
        if content:
            filename = os.path.join(output_dir, f"{name}.m3u8")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
    
    # Save master playlist
    master_file = os.path.join(output_dir, f"master_{timestamp}.m3u8")
    with open(master_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for name, content in results.items():
            if content:
                f.write(f"\n# {name.upper()}\n")
                # Extract first track URL for master playlist
                match = re.search(r'https://str.yodacdn.net/[^/]+/tracks/[^\n]+', content)
                if match:
                    f.write(match.group(0) + "\n")
    
    # Save metadata
    meta_file = os.path.join(output_dir, f"metadata_{timestamp}.json")
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "token": token,
            "channel_count": len([c for c in results.values() if c]),
            "channels": list(results.keys())
        }, f, indent=2)
    
    print(f"✅ Results saved to {output_dir}/")
    print(f"   - Individual channel files: {len([c for c in results.values() if c])} channels")
    print(f"   - Master playlist: master_{timestamp}.m3u8")
    print(f"   - Metadata: metadata_{timestamp}.json")
    return timestamp

def main():
    """Main function"""
    print("🚀 Starting Yoda M3U8 Extractor...")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📺 Total channels: {len(names)}")
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
    success_count = 0
    
    for name in names:
        content = process_channel(name, token)
        if content:
            results[name] = content
            success_count += 1
            print(f"   ✅ {name} - OK")
        else:
            results[name] = None
            print(f"   ❌ {name} - FAILED")
    
    print("-" * 50)
    print(f"📊 Success rate: {success_count}/{len(names)} channels")
    
    # Save results
    if success_count > 0:
        timestamp = save_results(results, token)
        print("✅ Process completed successfully!")
        print(f"📁 Output files saved with timestamp: {timestamp}")
    else:
        print("❌ No channels were processed successfully.")
        exit(1)

if __name__ == "__main__":
    main()
