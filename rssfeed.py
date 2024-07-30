import json
import os
import re
import sys
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime

# Load configuration from config.json
def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

# Fetch data from the API with the given page number
def fetch_data(api_link, page_number):
    url = f"{api_link}{page_number}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch data from {url}, status code: {response.status_code}")
        sys.exit(1)

# Filter entries based on include and exclude regex
def filter_entries(entries, include_regex, exclude_regex):
    filtered_entries = []
    include_pattern = re.compile(include_regex) if include_regex else None
    exclude_pattern = re.compile(exclude_regex) if exclude_regex else None

    for entry in entries:
        title = entry.get("title", "")
        if include_pattern and not include_pattern.search(title):
            continue
        if exclude_pattern and exclude_pattern.search(title):
            continue
        filtered_entries.append(entry)

    return filtered_entries

# Load existing IDs from the XML file, if it exists
def load_existing_ids(xml_file_name):
    existing_ids = set()
    file_path = os.path.join('rssfeed', xml_file_name)
    if os.path.exists(file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()
        for item in root.findall('.//item'):
            entry_id = item.find('id')
            if entry_id is not None:
                existing_ids.add(entry_id.text)
    return existing_ids

# Create or update the XML file with new entries
def update_xml_file(xml_file_name, channel_title, channel_link, entries):
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')

    # Add channel title and link
    title_element = ET.SubElement(channel, 'title')
    title_element.text = channel_title

    link_element = ET.SubElement(channel, 'link')
    link_element.text = channel_link

    for entry in entries:
        item = ET.SubElement(channel, 'item')

        # Add item details
        id_element = ET.SubElement(item, 'id')
        id_element.text = str(entry['id'])

        title_element = ET.SubElement(item, 'title')
        title_element.text = f"<![CDATA[{entry['title']}]]>"

        link_element = ET.SubElement(item, 'link')
        link_element.text = entry['torrent_url']

        guid_element = ET.SubElement(item, 'guid')
        guid_element.text = entry['torrent_url']

        pub_date_element = ET.SubElement(item, 'pubDate')
        pub_date_element.text = datetime.utcfromtimestamp(entry['timestamp']).strftime('%a, %d %b %Y %H:%M:%S +0000')

        # Construct the description
        size_mb = entry['total_size'] / (1024 * 1024)
        size_str = f"{size_mb:.2f} MiB"

        seeders = entry['seeders']
        leechers = entry['leechers']

        anidb_aid = entry['anidb_aid'] if entry.get('anidb_aid') else "N/A"
        
        # Determine which ID to use and construct the hyperlink
        nyaa_id = entry.get("nyaa_id")
        tosho_id = entry.get("tosho_id")
        anidex_id = entry.get("anidex_id")
        
        hyperlink = ""
        id_info = ""
        
        if nyaa_id:
            id_info = f"Nyaa: {nyaa_id}"
            hyperlink = f'<a href="https://nyaa.si/view/{nyaa_id}">{entry["title"]}</a>'
        elif tosho_id:
            id_info = f"Tosho: {tosho_id}"
            hyperlink = f'<a href="https://www.tokyotosho.info/details.php?id={tosho_id}">{entry["title"]}</a>'
        elif anidex_id:
            id_info = f"AniDex: {anidex_id}"
            hyperlink = f'<a href="https://anidex.info/torrent/{anidex_id}">{entry["title"]}</a>'

        description_content = f"{size_str} | Seeders: {seeders} | Leechers: {leechers} | AniDB: {anidb_aid} | {id_info} | {hyperlink}"

        description_element = ET.SubElement(item, 'description')
        description_element.text = f"<![CDATA[{description_content}]]>"

    # Convert to XML string
    xml_str = ET.tostring(rss, encoding='utf-8')

    # Pretty print the XML string
    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

    # Remove extra blank lines between elements
    pretty_xml_str = "\n".join(line for line in pretty_xml_str.splitlines() if line.strip())

    # Fix CDATA section being escaped
    pretty_xml_str = pretty_xml_str.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

    # Write to file
    file_path = os.path.join('rssfeed', xml_file_name)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(pretty_xml_str)

def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py feed_number page_number")
        sys.exit(1)

    feed_number = int(sys.argv[1])
    page_number = int(sys.argv[2])

    config = load_config()
    feeds = config['feeds']

    # Find the feed corresponding to feed_number
    selected_feed = None
    for feed in feeds:
        if feed['number'] == feed_number:
            selected_feed = feed
            break

    if not selected_feed:
        print(f"Feed number {feed_number} not found.")
        sys.exit(1)

    # Fetch data from the API
    entries = fetch_data(selected_feed['api_link'], page_number)

    # Filter entries
    filtered_entries = filter_entries(entries, selected_feed['include_regex'], selected_feed['exclude_regex'])

    # Load existing IDs from the XML file
    existing_ids = load_existing_ids(selected_feed['xml_file_name'])

    # Only keep unique entries (not already in the XML)
    unique_entries = [entry for entry in filtered_entries if str(entry['id']) not in existing_ids]

    # Update the XML file with new unique entries
    update_xml_file(selected_feed['xml_file_name'], selected_feed['name'], selected_feed['link'], unique_entries)

    print(f"Processed {len(unique_entries)} new entries for feed {selected_feed['name']}.")

if __name__ == "__main__":
    main()
