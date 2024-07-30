import json
import requests
import re
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import sys
from io import StringIO

def fetch_data(api_link, max_page):
    data = []
    for page in range(1, max_page + 1):
        response = requests.get(f"{api_link}{page}")
        if response.status_code == 200:
            data.extend(response.json())
        else:
            print(f"Failed to fetch data from page {page}")
    return data

def extract_ids(items):
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
    return ids

def filter_items(items, include_regex, exclude_regex):
    filtered_items = []
    include_pattern = re.compile(include_regex) if include_regex else None
    exclude_pattern = re.compile(exclude_regex) if exclude_regex else None

    for item in items:
        title = item.get('title', '')
        if include_pattern and not include_pattern.search(title):
            continue
        if exclude_pattern and exclude_pattern.search(title):
            continue
        filtered_items.append(item)
    
    return filtered_items

def item_exists(existing_ids, item):
    nyaa_id = item.get('nyaa_id')
    nyaa_subdom = item.get('nyaa_subdom')
    tosho_id = item.get('tosho_id')
    anidex_id = item.get('anidex_id')

    if nyaa_id and f"nyaa_id:{nyaa_id}" in existing_ids:
        return True
    if nyaa_subdom and f"nyaa_subdom:{nyaa_subdom}" in existing_ids:
        return True
    if tosho_id and f"tosho_id:{tosho_id}" in existing_ids:
        return True
    if anidex_id and f"anidex_id:{anidex_id}" in existing_ids:
        return True
    return False

def create_temp_xml(new_items):
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
        description.text = f"<![CDATA[{item['total_size'] // (1024 * 1024)} MiB | Seeders: {item['seeders']} | Leechers: {item['leechers']} | AniDB: {item['anidb_aid']} | <a href=\"{item['link']}\">{item['title']}</a>]]>"
    
    # Convert the ElementTree to a string
    xml_str = ET.tostring(rss, encoding="utf-8", method="xml")

    # Pretty print the XML string
    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

    # Remove extra blank lines between elements
    pretty_xml_str = "\n".join(line for line in pretty_xml_str.splitlines() if line.strip())

    # Fix CDATA section being escaped
    pretty_xml_str = pretty_xml_str.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

    return pretty_xml_str

def merge_xml_strings(old_xml_str, temp_xml_str):
    # Extract the RSS channel tag from both old and new XML
    old_channel = old_xml_str.split('<channel>')[1].split('</channel>')[0]
    temp_channel = temp_xml_str.split('<channel>')[1].split('</channel>')[0]

    # Merge the XML content
    merged_data = old_xml_str.replace('</channel>', temp_channel + '</channel>')

    return merged_data

def main(feed_number, max_page):
    with open('config.json') as config_file:
        config = json.load(config_file)
    
    feed_config = next((feed for feed in config['feeds'] if feed['number'] == feed_number), None)
    if not feed_config:
        print(f"No feed found with number {feed_number}")
        return
    
    items = fetch_data(feed_config['api_link'], max_page)
    filtered_items = filter_items(items, feed_config['include_regex'], feed_config['exclude_regex'])
    
    output_xml_path = os.path.join('rssfeed', feed_config['xml_file_name'])
    old_xml_str = ''
    if os.path.exists(output_xml_path):
        with open(output_xml_path, 'r', encoding='utf-8') as old_file:
            old_xml_str = old_file.read()
        
        old_ids = extract_ids(json.loads(old_xml_str).get('items', []))
    else:
        old_ids = set()
    
    new_ids = extract_ids(filtered_items)
    new_items = [item for item in filtered_items if not item_exists(old_ids, item)]
    
    if not new_items:
        print("No New Update")
        return
    
    # Create temporary XML for new items
    temp_xml_str = create_temp_xml(new_items)
    
    if old_xml_str:
        merged_xml_str = merge_xml_strings(old_xml_str, temp_xml_str)
        with open(output_xml_path, 'w', encoding='utf-8') as output_file:
            output_file.write(merged_xml_str)
    else:
        with open(output_xml_path, 'w', encoding='utf-8') as output_file:
            output_file.write(temp_xml_str)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: rssfeed.py feed_number page_number")
        sys.exit(1)
    
    feed_number = int(sys.argv[1])
    max_page = int(sys.argv[2])
    
    main(feed_number, max_page)
