import json
import requests
import re
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import sys

def fetch_data(api_link, max_page):
    print(f"Fetching data from API link: {api_link}")
    data = []
    for page in range(1, max_page + 1):
        print(f"Fetching page {page}...")
        response = requests.get(f"{api_link}{page}")
        if response.status_code == 200:
            data.extend(response.json())
            print(f"Page {page} fetched successfully.")
        else:
            print(f"Failed to fetch data from page {page}. Status code: {response.status_code}")
    print(f"Total items fetched: {len(data)}")
    return data

def extract_ids_from_xml(xml_str):
    print("Extracting IDs from XML...")
    root = ET.fromstring(xml_str)
    existing_ids = set()
    for item in root.findall('.//item'):
        for id_type in ['nyaa_id', 'nyaa_subdom', 'tosho_id', 'anidex_id']:
            element = item.find(id_type)
            if element is not None and element.text:
                existing_ids.add(f"{id_type}:{element.text}")
    print(f"Existing IDs extracted: {existing_ids}")
    return existing_ids

def extract_ids(items):
    print("Extracting IDs from new items...")
    ids = set()
    for item in items:
        nyaa_id = item.get('nyaa_id')
        nyaa_subdom = item.get('nyaa_subdom')
        tosho_id = item.get('tosho_id')
        anidex_id = item.get('anidex_id')
        if nyaa_id:
            ids.add(f"nyaa_id:{nyaa_id}")
        elif nyaa_subdom:
            ids.add(f"nyaa_subdom:{nyaa_subdom}")
        elif tosho_id:
            ids.add(f"tosho_id:{tosho_id}")
        elif anidex_id:
            ids.add(f"anidex_id:{anidex_id}")
    print(f"New IDs extracted: {ids}")
    return ids

def filter_items(items, include_regex, exclude_regex):
    print("Filtering items...")
    filtered_items = []
    include_pattern = re.compile(include_regex) if include_regex else None
    exclude_pattern = re.compile(exclude_regex) if exclude_regex else None

    for item in items:
        title = item.get('title', '')
        if include_pattern and not include_pattern.search(title):
            print(f"Item excluded by include_regex: {title}")
            continue
        if exclude_pattern and exclude_pattern.search(title):
            print(f"Item excluded by exclude_regex: {title}")
            continue
        filtered_items.append(item)
    
    print(f"Filtered items count: {len(filtered_items)}")
    return filtered_items

def item_exists(existing_ids, item):
    print("Checking if item exists...")
    nyaa_id = item.get('nyaa_id')
    nyaa_subdom = item.get('nyaa_subdom')
    tosho_id = item.get('tosho_id')
    anidex_id = item.get('anidex_id')

    if nyaa_id and f"nyaa_id:{nyaa_id}" in existing_ids:
        print(f"Item exists with nyaa_id: {nyaa_id}")
        return True
    if nyaa_subdom and f"nyaa_subdom:{nyaa_subdom}" in existing_ids:
        print(f"Item exists with nyaa_subdom: {nyaa_subdom}")
        return True
    if tosho_id and f"tosho_id:{tosho_id}" in existing_ids:
        print(f"Item exists with tosho_id: {tosho_id}")
        return True
    if anidex_id and f"anidex_id:{anidex_id}" in existing_ids:
        print(f"Item exists with anidex_id: {anidex_id}")
        return True
    return False

def create_temp_xml(new_items):
    print("Creating temporary XML...")
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    for item in new_items:
        item_element = ET.SubElement(channel, "item")
        
        title = ET.SubElement(item_element, "title")
        title.text = f"<![CDATA[{item['title']}]]>"
        
        link = ET.SubElement(item_element, "link")
        link.text = item['torrent_url']
        
        guid = ET.SubElement(item_element, "guid")
        guid.text = item['torrent_url']
        
        nyaa_id = ET.SubElement(item_element, "nyaa_id")
        nyaa_id.text = str(item['nyaa_id']) if item.get('nyaa_id') else ''
        
        pubDate = ET.SubElement(item_element, "pubDate")
        pubDate.text = datetime.utcfromtimestamp(item['timestamp']).strftime('%a, %d %b %Y %H:%M:%S +0000')
        
        description = ET.SubElement(item_element, "description")
        hyperlink = ''
        if item.get("nyaa_id"):
            hyperlink = f'<a href="https://nyaa.si/view/{item["nyaa_id"]}">{item["title"]}</a>'
        elif item.get("tosho_id"):
            hyperlink = f'<a href="https://www.tokyotosho.info/details.php?id={item["tosho_id"]}">{item["title"]}</a>'
        elif item.get("anidex_id"):
            hyperlink = f'<a href="https://anidex.info/torrent/{item["anidex_id"]}">{item["title"]}</a>'
        elif item.get("nyaa_subdom"):
            hyperlink = f'<a href="{item["link"]}">{item["title"]}</a>'
        
        description.text = f"<![CDATA[{item.get('total_size', 'Unknown Size') // (1024 * 1024)} MiB | Seeders: {item.get('seeders', 'Unknown')} | Leechers: {item.get('leechers', 'Unknown')} | AniDB: {item.get('anidb_aid', 'Unknown')} | {hyperlink}]]>"
    
    # Convert the ElementTree to a string
    xml_str = ET.tostring(rss, encoding="utf-8", method="xml")

    # Pretty print the XML string
    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

    # Remove extra blank lines between elements
    pretty_xml_str = "\n".join(line for line in pretty_xml_str.splitlines() if line.strip())

    # Fix CDATA section being escaped
    pretty_xml_str = pretty_xml_str.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

    print("Temporary XML created.")
    return pretty_xml_str

def merge_xml_strings(old_xml_str, temp_xml_str):
    print("Merging old and new XML...")
    # Extract the RSS channel tag from both old and new XML
    old_channel = old_xml_str.split('<channel>')[1].split('</channel>')[0]
    temp_channel = temp_xml_str.split('<channel>')[1].split('</channel>')[0]

    # Merge the XML content
    merged_data = old_xml_str.replace('</channel>', temp_channel + '</channel>')

    print("XML merged.")
    return merged_data

def sort_xml_by_pubDate(xml_str):
    print("Sorting XML by pubDate...")
    # Extract the items
    items = re.findall(r'(<item>.*?</item>)', xml_str, re.DOTALL)
    
    # Sort items based on pubDate
    def get_pubDate(item):
        match = re.search(r'<pubDate>(.*?)</pubDate>', item)
        return match.group(1) if match else ''

    sorted_items = sorted(items, key=lambda x: datetime.strptime(get_pubDate(x), '%a, %d %b %Y %H:%M:%S +0000'), reverse=True)

    # Rebuild XML with sorted items
    channel_start = xml_str.find('<channel>')
    channel_end = xml_str.find('</channel>')
    sorted_xml = xml_str[:channel_start + len('<channel>')] + ''.join(sorted_items) + xml_str[channel_end:]

    print("XML sorted.")
    return sorted_xml

def main(feed_number, max_page):
    print(f"Starting main function with feed_number={feed_number} and max_page={max_page}")
    
    with open('config.json') as config_file:
        config = json.load(config_file)
    
    feed_config = next((feed for feed in config['feeds'] if feed['number'] == feed_number), None)
    if not feed_config:
        print(f"No feed found with number {feed_number}")
        return
    
    items = fetch_data(feed_config['api_link'], max_page)
    filtered_items = filter_items(items, feed_config['include_regex'], feed_config['exclude_regex'])
    
    output_dir = 'rssfeed'
    output_xml_path = os.path.join(output_dir, feed_config['xml_file_name'])
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Output directory created: {output_dir}")
    
    if os.path.exists(output_xml_path):
        print(f"Loading existing XML file: {output_xml_path}")
        with open(output_xml_path, 'r', encoding='utf-8') as old_file:
            old_xml_str = old_file.read()
        
        old_ids = extract_ids_from_xml(old_xml_str)
    else:
        print(f"XML file does not exist. Creating new file: {output_xml_path}")
        old_ids = set()
        old_xml_str = '<rss version="2.0"><channel></channel></rss>'
    
    new_ids = extract_ids(filtered_items)
    new_items = [item for item in filtered_items if not item_exists(old_ids, item)]
    
    if not new_items:
        print("No New Update")
        return
    
    # Create temporary XML for new items
    temp_xml_str = create_temp_xml(new_items)
    
    # Merge old and new XML
    merged_xml_str = merge_xml_strings(old_xml_str, temp_xml_str)
    
    # Sort XML by pubDate
    sorted_xml_str = sort_xml_by_pubDate(merged_xml_str)
    
    # Write to output file
    with open(output_xml_path, 'w', encoding='utf-8') as output_file:
        output_file.write(sorted_xml_str)
    
    print(f"Updated XML file written to: {output_xml_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: rssfeed.py feed_number page_number")
        sys.exit(1)
    
    feed_number = int(sys.argv[1])
    max_page = int(sys.argv[2])
    
    main(feed_number, max_page)
