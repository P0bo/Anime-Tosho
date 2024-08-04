import json
import os
import re
import sys
import requests
from datetime import datetime

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def fetch_data(api_link):
    try:
        response = requests.get(api_link, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data from {api_link}, error: {e}")
        return None

def extract_text(pattern, text):
    match = re.search(pattern, text)
    return match.group(1) if match else None

def process_item(item_text):
    # Define patterns to extract elements
    patterns = {
        'title': r'<title>(.*?)</title>',
        'link': r'<link>(.*?)</link>',
        'guid': r'<guid[^>]*>(.*?)</guid>',
        'pubDate': r'<pubDate>(.*?)</pubDate>',
        'seeders': r'<(?:ns0:|nyaa:)?seeders>(.*?)</(?:ns0:|nyaa:)?seeders>',
        'leechers': r'<(?:ns0:|nyaa:)?leechers>(.*?)</(?:ns0:|nyaa:)?leechers>',
        'downloads': r'<(?:ns0:|nyaa:)?downloads>(.*?)</(?:ns0:|nyaa:)?downloads>',
        'size': r'<(?:ns0:|nyaa:)?size>(.*?)</(?:ns0:|nyaa:)?size>',
        'description': r'<description>(.*?)</description>',
        'trusted': r'<(?:ns0:|nyaa:)?trusted>(.*?)</(?:ns0:|nyaa:)?trusted>',
        'remake': r'<(?:ns0:|nyaa:)?remake>(.*?)</(?:ns0:|nyaa:)?remake>'
    }
    
    item_data = {}
    for key, pattern in patterns.items():
        item_data[key] = extract_text(pattern, item_text)

    return item_data

def parse_xml(xml_content):
    items = re.findall(r'<item.*?>(.*?)</item>', xml_content, re.DOTALL)
    entries = []
    
    for item_text in items:
        item_data = process_item(item_text)
        if (item_data['title'] and item_data['link'] and item_data['guid'] and
            item_data['pubDate'] and item_data['size'] and item_data['seeders'] and
            item_data['leechers'] and item_data['downloads']):
            entries.append(item_data)
        else:
            print(f"Skipping item due to missing elements: {item_text[:100]}...")  # Print a snippet for debugging
    
    return entries

def filter_entries(entries, include_regex, exclude_regex):
    filtered_entries = []
    include_pattern = re.compile(include_regex, re.IGNORECASE) if include_regex else None
    exclude_pattern = re.compile(exclude_regex, re.IGNORECASE) if exclude_regex else None

    for entry in entries:
        title = entry.get("title", "")

        if include_pattern and not include_pattern.search(title):
            continue
        if exclude_pattern and exclude_pattern.search(title):
            continue

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

    id_pattern = re.compile(r'<guid isPermaLink="true">https://nyaa\.si/view/(\d+)</guid>')
    return set(id_pattern.findall(existing_xml))

def create_xml_entries(feed_name, feed_link, entries, existing_ids, domain):
    new_entries = []

    for entry in entries:
        entry_id = str(entry['guid'].split('/')[-1])
        if entry_id in existing_ids:
            continue

        title = entry['title']
        torrent_url = entry['link']
        pub_date = entry['pubDate']

        size_str = entry['size']
        size_value, size_unit = re.match(r'([0-9.]+)\s*(MiB|GiB)', size_str).groups()
        size_mb = float(size_value) * (1024 if size_unit == 'GiB' else 1)  # Convert GiB to MiB

        seeders = entry.get('seeders', 0)
        leechers = entry.get('leechers', 0)
        downloads = entry.get('downloads', 0)
        trusted = entry.get('trusted', 'Unknown')
        remake = entry.get('remake', 'Unknown')

        # Replace the domain in the torrent URL
        torrent_url = re.sub(r'https://nyaa\.si/', f'{domain}/', torrent_url)
        
        hyperlink = f'<a href="{entry["guid"]}">{title}</a>'
        description_content = (
            f"{size_mb:.2f} MiB | Seeders: {seeders} | Leechers: {leechers} | "
            f"Downloads: {downloads} | Nyaa: {entry_id} | Trusted: {trusted} | Remake: {remake} | {hyperlink}"
        )

        new_entry = f"""
<item>
  <guid isPermaLink="true">{entry['guid']}</guid>
  <title><![CDATA[{title}]]></title>
  <link>{torrent_url}</link>
  <pubDate>{pub_date}</pubDate>
  <description><![CDATA[{description_content}]]></description>
</item>"""
        new_entries.append(new_entry.strip())

    return new_entries

def merge_xml_data(existing_xml, new_entries, feed_name, feed_link):
    if existing_xml is None:
        existing_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>{feed_name}</title>
  <link>{feed_link}</link>
</channel>
</rss>"""
    
    channel_start = existing_xml.find("<channel>")
    channel_end = existing_xml.find("</channel>")

    if channel_start == -1 or channel_end == -1:
        raise ValueError("Invalid XML structure: Missing <channel> tags.")

    merged_xml = (
        existing_xml[:channel_end] +
        "\n".join(new_entries) +
        "\n" +
        existing_xml[channel_end:]
    )

    return merged_xml.strip()

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py feed_number")
        sys.exit(1)

    feed_number = int(sys.argv[1])

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

    print("Processing feed...")

    xml_data = fetch_data(selected_feed['api_link'])
    if xml_data:
        entries = parse_xml(xml_data)

        filtered_entries = filter_entries(
            entries, 
            selected_feed['include_regex'], 
            selected_feed['exclude_regex']
        )

        domain = selected_feed['link'].rstrip('/')  # Ensure no trailing slash
        new_entries = create_xml_entries(selected_feed['name'], selected_feed['link'], filtered_entries, existing_ids, domain)

        existing_ids.update(entry['guid'].split('/')[-1] for entry in filtered_entries)

        all_new_entries.extend(new_entries)

        print(f"Processed {len(new_entries)} new entries.")

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
