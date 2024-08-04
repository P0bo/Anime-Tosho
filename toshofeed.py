import json
import os
import re
import sys
import requests
from datetime import datetime

def load_config():
    with open('toshoconfig.json', 'r') as f:
        return json.load(f)

def fetch_data(api_link, page_number):
    url = f"{api_link}{page_number}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data from {url}, error: {e}")
        return []  # Return empty list on failure

def filter_entries(entries, include_regex, exclude_regex, single_file, images):
    filtered_entries = []
    include_pattern = re.compile(include_regex) if include_regex else None
    exclude_pattern = re.compile(exclude_regex) if exclude_regex else None

    for entry in entries:
        title = entry.get("title", "")
        num_files = entry.get("num_files", 0)

        # Apply regex filters
        if include_pattern and not include_pattern.search(title):
            continue
        if exclude_pattern and exclude_pattern.search(title):
            continue

        # Apply single file filter
        if single_file == 1 and num_files != 1:
            continue
        if single_file == 0 and num_files <= 1:
            continue

        # Check if the feed has images defined and filter accordingly
        if images:
            anidb_aid = entry.get('anidb_aid')
            if not anidb_aid or str(anidb_aid) not in images:
                continue  # Skip entries without defined images
        filtered_entries.append(entry)

    return filtered_entries

def load_existing_xml(xml_file_name):
    file_path = os.path.join('rssfeed', xml_file_name)
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    return None

def extract_existing_ids(existing_xml):
    if not existing_xml:
        return set()

    # Use regex to extract <id>...</id> from the XML
    id_pattern = re.compile(r'<id>(\d+)</id>')
    return set(id_pattern.findall(existing_xml))

def create_xml_entries(feed_name, feed_link, entries, existing_ids, images):
    new_entries = []
    images_added_count = 0  # Counter for added images

    for entry in entries:
        entry_id = str(entry['id'])
        # Skip if entry ID already exists
        if entry_id in existing_ids:
            continue

        title = entry['title']
        torrent_url = entry['torrent_url']
        timestamp = entry['timestamp']

        size_mb = entry['total_size'] / (1024 * 1024)
        size_str = f"{size_mb:.2f} MiB"

        seeders = entry['seeders']
        leechers = entry['leechers']

        anidb_aid = entry.get('anidb_aid', "N/A")  # Ensure there's a default value

        nyaa_id = entry.get("nyaa_id")
        tosho_id = entry.get("tosho_id")
        anidex_id = entry.get("anidex_id")

        hyperlink = ""
        id_info = ""

        if nyaa_id:
            id_info = f"Nyaa: {nyaa_id}"
            hyperlink = f'<a href="https://nyaa.si/view/{nyaa_id}">{title}</a>'
        elif tosho_id:
            id_info = f"Tosho: {tosho_id}"
            hyperlink = f'<a href="https://www.tokyotosho.info/details.php?id={tosho_id}">{title}</a>'
        elif anidex_id:
            id_info = f"AniDex: {anidex_id}"
            hyperlink = f'<a href="https://anidex.info/torrent/{anidex_id}">{title}</a>'

        file_info = f"Files: {entry['num_files']}" if entry['num_files'] > 1 else "File: 1"
        
        # Check for image based on AniDB ID
        image_tag = ""
        # Convert AniDB ID to string to match JSON keys
        anidb_aid_str = str(anidb_aid)
        if anidb_aid_str in images:
            image_id = images[anidb_aid_str]
            image_tag = f'<br><img src="https://cdn-eu.anidb.net/images/main/{image_id}.jpg" alt="Image" />'
            images_added_count += 1  # Increment the image counter

        description_content = f"{size_str} | {file_info} | Seeders: {seeders} | Leechers: {leechers} | AniDB: {anidb_aid} | {id_info} | {hyperlink}{image_tag}"

        pub_date = datetime.utcfromtimestamp(timestamp).strftime('%a, %d %b %Y %H:%M:%S +0000')

        new_entry = f"""
<item>
  <id>{entry_id}</id>
  <title><![CDATA[{title}]]></title>
  <link>{torrent_url}</link>
  <guid>{torrent_url}</guid>
  <pubDate>{pub_date}</pubDate>
  <description><![CDATA[{description_content}]]></description>
</item>"""
        new_entries.append(new_entry.strip())

    # Print the total number of images added
    if images_added_count > 0:
        print(f"Total Images added: {images_added_count}")
    else:
        print("No Images added")

    return new_entries

def merge_xml_data(existing_xml, new_entries, feed_name, feed_link):
    if existing_xml is None:
        # Create a new XML structure if it doesn't exist
        existing_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>{feed_name}</title>
  <link>{feed_link}</link>
</channel>
</rss>"""
    
    # Define the start and end of the <channel> tag
    channel_start = existing_xml.find("<channel>")
    channel_end = existing_xml.find("</channel>")

    if channel_start == -1 or channel_end == -1:
        raise ValueError("Invalid XML structure: Missing <channel> tags.")

    # Insert new entries inside the <channel> tags
    merged_xml = (
        existing_xml[:channel_end] +
        "\n".join(new_entries) +
        "\n" +
        existing_xml[channel_end:]
    )

    return merged_xml.strip()

def main():
    if len(sys.argv) != 4:
        print("Usage: python script.py feed_number start_page end_page")
        sys.exit(1)

    feed_number = int(sys.argv[1])
    start_page = int(sys.argv[2])
    end_page = int(sys.argv[3])

    config = load_config()
    feeds = config['feeds']

    selected_feed = None
    for feed in feeds:
        if feed['number'] == feed_number:
            selected_feed = feed
            break

    if not selected_feed:
        print(f"Feed number {feed_number} not found.")
        sys.exit(1)

    existing_xml = load_existing_xml(selected_feed['xml_file_name'])
    existing_ids = extract_existing_ids(existing_xml)

    all_new_entries = []

    for page_number in range(start_page, end_page + 1):
        print(f"Processing page {page_number}...")

        entries = fetch_data(selected_feed['api_link'], page_number)

        # Extract images mapping if exists
        images = {}
        if 'image' in selected_feed:
            images = selected_feed['image'][0]  # Assuming single image mapping for the feed

        filtered_entries = filter_entries(
            entries, 
            selected_feed['include_regex'], 
            selected_feed['exclude_regex'], 
            selected_feed['single_file'],
            images
        )

        new_entries = create_xml_entries(selected_feed['name'], selected_feed['link'], filtered_entries, existing_ids, images)

        existing_ids.update(entry['id'] for entry in filtered_entries)

        all_new_entries.extend(new_entries)

        print(f"Page {page_number}: Processed {len(new_entries)} new entries.")

    # Only merge and write to file if there are new entries
    if all_new_entries:
        merged_xml = merge_xml_data(existing_xml, all_new_entries, selected_feed['name'], selected_feed['link'])

        file_path = os.path.join('rssfeed', selected_feed['xml_file_name'])
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(merged_xml)

        print(f"Total new entries merged: {len(all_new_entries)}")
    else:
        print("No new entries to merge. The XML file was not modified.")

if __name__ == "__main__":
    main()
