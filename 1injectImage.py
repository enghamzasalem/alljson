import json
import requests
import base64
import time
import os
import re
from urllib.parse import quote
from bs4 import BeautifulSoup

def download_image_to_base64(image_url):
    """Download image from URL and convert to base64"""
    try:
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        
        # Convert to base64
        image_base64 = base64.b64encode(response.content).decode('utf-8')
        
        # Determine image type from content-type header
        content_type = response.headers.get('content-type', 'image/jpeg')
        if 'png' in content_type:
            image_type = 'image/png'
        elif 'gif' in content_type:
            image_type = 'image/gif'
        elif 'webp' in content_type:
            image_type = 'image/webp'
        else:
            image_type = 'image/jpeg'
        
        return {
            'data': image_base64,
            'type': image_type,
            'url': image_url
        }
    except Exception as e:
        print(f"Error downloading image {image_url}: {e}")
        return None

def search_google_custom_search(query, api_key, cx, max_results=3):
    """Search Google Custom Search API and return results"""
    try:
        # Encode the query for URL
        encoded_query = quote(query)
        
        # Build the API URL
        url = f"https://www.googleapis.com/customsearch/v1"
        params = {
            'key': api_key,
            'cx': cx,
            'q': query,
            'num': max_results
        }
        
        print(f"Searching for: {query}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        return response.json()
    except Exception as e:
        print(f"Error searching for '{query}': {e}")
        return None

def scrape_bing_images_web(query, max_results=3):
    """Scrape Bing Images search results directly from the web"""
    try:
        # Create headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Build Bing Images search URL - request larger images
        search_url = f"https://www.bing.com/images/search?q={quote(query)}&first=1&qft=+filterui:imagesize-large"
        
        print(f"Web scraping Bing Images for: {query}")
        response = requests.get(search_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find image URLs in the page
        image_urls = []
        
        # Method 1: Look for Bing's specific image containers with murl (high-res images)
        print("Looking for Bing iusc containers with murl...")
        image_containers = soup.find_all('a', {'class': 'iusc'})
        for container in image_containers:
            if container.get('m'):
                try:
                    m_data = json.loads(container.get('m'))
                    if 'murl' in m_data and m_data['murl']:
                        murl = m_data['murl']
                        if murl.startswith('http') and murl not in image_urls:
                            image_urls.append(murl)
                            print(f"Found high-res image from iusc murl: {murl}")
                            if len(image_urls) >= max_results:
                                break
                except json.JSONDecodeError as e:
                    print(f"Error parsing m data: {e}")
                    continue
                except Exception as e:
                    print(f"Error processing container: {e}")
                    continue
        
        # Method 2: Look for data-src attributes (lazy-loaded images)
        if len(image_urls) < max_results:
            print("Looking for data-src attributes...")
            img_tags = soup.find_all('img', {'data-src': True})
            for img in img_tags:
                src = img.get('data-src')
                if src and src.startswith('http') and src not in image_urls:
                    image_urls.append(src)
                    print(f"Found image from data-src: {src}")
                    if len(image_urls) >= max_results:
                        break
        
        # Method 3: Look for regular src attributes
        if len(image_urls) < max_results:
            print("Looking for regular src attributes...")
            img_tags = soup.find_all('img', {'src': True})
            for img in img_tags:
                src = img.get('src')
                if src and src.startswith('http') and src not in image_urls:
                    image_urls.append(src)
                    print(f"Found image from src: {src}")
                    if len(image_urls) >= max_results:
                        break
        
        # Method 4: Look for JSON data in script tags (Bing specific)
        if len(image_urls) < max_results:
            print("Looking for JSON data in script tags...")
            script_tags = soup.find_all('script')
            for script in script_tags:
                if script.string:
                    # Look for image URLs in Bing's JSON structures
                    # Bing often uses "murl" for image URLs
                    matches = re.findall(r'"murl":"([^"]+\.(?:jpg|jpeg|png|gif|webp))"', script.string)
                    for match in matches:
                        if match not in image_urls and len(image_urls) < max_results:
                            image_urls.append(match)
                            print(f"Found image from script murl: {match}")
                    
                    # Also look for other Bing image URL patterns
                    matches2 = re.findall(r'"url":"([^"]+\.(?:jpg|jpeg|png|gif|webp))"', script.string)
                    for match in matches2:
                        if match not in image_urls and len(image_urls) < max_results:
                            image_urls.append(match)
                            print(f"Found image from script url: {match}")
        
        # Method 5: Look for href attributes that contain image URLs
        if len(image_urls) < max_results:
            print("Looking for href attributes with image URLs...")
            href_links = soup.find_all('a', href=True)
            for link in href_links:
                href = link.get('href')
                if href and 'mediaurl=' in href:
                    # Extract the mediaurl parameter
                    mediaurl_match = re.search(r'mediaurl=([^&]+)', href)
                    if mediaurl_match:
                        mediaurl = requests.utils.unquote(mediaurl_match.group(1))
                        if mediaurl.startswith('http') and mediaurl not in image_urls:
                            image_urls.append(mediaurl)
                            print(f"Found image from href mediaurl: {mediaurl}")
                            if len(image_urls) >= max_results:
                                break
        
        # Filter out invalid URLs and duplicates
        filtered_urls = []
        for url in image_urls:
            if url and url.startswith('http') and url not in filtered_urls:
                # Prefer larger images (check for size indicators in URL)
                if any(size_indicator in url.lower() for size_indicator in ['large', 'original', 'full', 'hd', '4k', '3840', '2160', '1920', '1080']):
                    filtered_urls.insert(0, url)  # Put larger images first
                else:
                    filtered_urls.append(url)
                if len(filtered_urls) >= max_results:
                    break
        
        print(f"Bing web scraping found {len(filtered_urls)} images")
        return filtered_urls
        
    except Exception as e:
        print(f"Error web scraping Bing for '{query}': {e}")
        return []

def extract_cse_images_from_results(search_results):
    """Extract image URLs from Google Custom Search results - from metatags with 'image' keys"""
    images = []
    
    if 'items' in search_results:
        for item in search_results['items']:
            # Check for metatags in pagemap
            if 'pagemap' in item and 'metatags' in item['pagemap']:
                metatags = item['pagemap']['metatags']
                
                # Look for any key that contains 'image'
                for meta in metatags:
                    for key, value in meta.items():
                        if 'image' in key.lower() and value and value.startswith('http'):
                            images.append(value)
                            print(f"Found image from metatag '{key}': {value}")
                            break  # Take only the first image from each result
                    if len(images) > 0:  # If we found an image in this result, move to next
                        break
    
    return images

def get_images_for_title(title, api_key, cx, max_images=3):
    """Get images for a title using API first, then Bing web scraping as fallback"""
    
    # Try Google Custom Search API first
    print(f"Trying Google Custom Search API for: {title}")
    search_results = search_google_custom_search(title, api_key, cx, max_images)
    
    if search_results and 'items' in search_results and len(search_results['items']) > 0:
        # Extract images from API results
        image_urls = extract_cse_images_from_results(search_results)
        if image_urls:
            print(f"API found {len(image_urls)} images")
            return image_urls
    
    # If API fails or no images found, try Bing web scraping
    print(f"API failed or no images found, trying Bing web scraping for: {title}")
    image_urls = scrape_bing_images_web(title, max_images)
    
    if image_urls:
        print(f"Bing web scraping found {len(image_urls)} images")
        return image_urls
    
    print("No images found from either method")
    return []

def process_single_json_file(json_file_path, api_key, cx, max_images=3):
    """Process a single JSON file and edit it in place"""
    
    # Read the original JSON file
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File {json_file_path} not found")
        return False
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON file {json_file_path}: {e}")
        return False
    
    print(f"Processing {json_file_path} with {len(data)} objects...")
    
    # Process each object
    for i, obj in enumerate(data):
        if 'title' in obj:
            title = obj['title']
            print(f"\nProcessing object {i+1}/{len(data)}: {title[:50]}...")
            
            # Get images using both API and web scraping methods
            image_urls = get_images_for_title(title, api_key, cx, max_images)
            
            if image_urls:
                # Download images and convert to base64
                downloaded_images = []
                for url in image_urls:
                    print(f"Downloading image: {url}")
                    image_data = download_image_to_base64(url)
                    if image_data:
                        downloaded_images.append(image_data)
                    time.sleep(0.5)  # Small delay to be respectful to servers
                
                # Inject images into the object
                obj['images'] = downloaded_images
                print(f"Added {len(downloaded_images)} images to object")
            else:
                print("No images found")
                obj['images'] = []
            
            # Add a longer delay between objects to respect API limits
            time.sleep(1)
        else:
            print(f"Object {i+1} has no title, skipping...")
            obj['images'] = []
    
    # Save the updated JSON back to the same file
    try:
        with open(json_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nUpdated {json_file_path} successfully!")
        return True
    except Exception as e:
        print(f"Error saving updated JSON {json_file_path}: {e}")
        return False

def process_multiple_json_files(api_key, cx, max_files=100, max_images=3):
    """Process multiple JSON files in the current directory"""
    
    # Get all JSON files in the current directory
    json_files = [f for f in os.listdir('.') if f.endswith('_en.json') and f != '1_with_images.json']
    
    # Sort files to process them in order
    json_files.sort()
    
    # Limit to max_files
    json_files = json_files[1:100]
    
    print(f"Found {len(json_files)} JSON files to process")
    print(f"Files to process: {json_files}")
    
    successful_files = 0
    failed_files = 0
    
    for i, json_file in enumerate(json_files):
        print(f"\n{'='*50}")
        print(f"Processing file {i+1}/{len(json_files)}: {json_file}")
        print(f"{'='*50}")
        
        if process_single_json_file(json_file, api_key, cx, max_images):
            successful_files += 1
        else:
            failed_files += 1
        
        # Add delay between files to respect API limits
        if i < len(json_files) - 1:  # Don't delay after the last file
            print(f"Waiting 2 seconds before next file...")
            time.sleep(2)
    
    print(f"\n{'='*50}")
    print(f"Processing complete!")
    print(f"Successful files: {successful_files}")
    print(f"Failed files: {failed_files}")
    print(f"Total files processed: {len(json_files)}")
    print(f"{'='*50}")

# Example usage
if __name__ == "__main__":
    # Google Custom Search API credentials
    API_KEY = "AIzaSyBOzy2muWRQFeJYtivqfon5i53AGTx3xp0"
    CX = "56f83a331f8044062"
    
    # Process 100 JSON files
    process_multiple_json_files(API_KEY, CX, max_files=100, max_images=3)
