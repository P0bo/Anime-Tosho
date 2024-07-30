import json
import requests
import re
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import sys

def fetch_data(api_link, max_page):
    data = []
    for page in range(1, max_page + 1):
        response = requests.get(f"{api_link}{page}")
        if response.status_code == 200:
            data.extend(response.json())
        else:
            print(f"Failed to fetch data from page {page}")
    return data

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

def item_exists(existing_items, item):
    nyaa_id = item.get('nyaa_id')
    nyaa_subdom = item.get('nyaa_subdom')
    tosho_id = item.get('tosho_id')
    anidex_id = item.get('anidex_id')

    for existing_item in existing_items:
        if (existing_item.find('nyaa_id') is not None and existing_item.find('nyaa_id').text == str(nyaa_id)) or \
           (existing_item.find('nyaa_subdom') is not None and existing_item.find('nyaa_subdom').text == str(nyaa_subdom)) or \
           (existing_item.find('tosho_id') is not None and existing_item.find('tosho_id').text == str(tosho_id)) or \
           (existing_item.find('anidex_id') is not None and existing_item.find('anidex_id').text == str(anidex_id)):
            return True
    return False

def create_rss(feed_config, items):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    title = ET.SubElement(channel, "title")
    title.text = feed_config['name']
    
    link = ET.SubElement(channel, "link")
    link.text = feed_config['link']
    
    for item in items:
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
    
    return rss

def update_rss_file(feed_config, new_items):
    file_path = os.path.join('rssfeed', feed_config['xml_file_name'])
    if os.path.exists(file_path):
        tree = ET.parse(file_path)
        root = tree.getroot()
        channel = root.find('channel')
        existing_items = channel.findall('item')
    else:
        os.makedirs('rssfeed', exist_ok=True)
        root = ET.Element("rss", version="2.0")
        channel = ET.SubElement(root, "channel")
        
        title = ET.SubElement(channel, "title")
        title.text = feed_config['name']
        
        link = ET.SubElement(channel, "link")
        link.text = feed_config['link']
        
        existing_items = []
    
    for item in new_items:
        if not item_exists(existing_items, item):
            item_element = ET.Element("item")
            
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
            
            channel.insert(0, item_element)  # Insert at the top
    
    # Convert the ElementTree to a string
    xml_str = ET.tostring(root, encoding="utf-8", method="xml")

    # Pretty print the XML string
    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

    # Remove extra blank lines between elements
    pretty_xml_str = "\n".join(line for line in pretty_xml_str.splitlines() if line.strip())

    # Fix CDATA section being escaped
    pretty_xml_str = pretty_xml_str.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(pretty_xml_str)

def main(feed_number, max_page):
    with open('config.json') as config_file:
        config = json.load(config_file)
    
    feed_config = next((feed for feed in config['feeds'] if feed['number'] == feed_number), None)
    if not feed_config:
        print(f"No feed found with number {feed_number}")
        return
    
    items = fetch_data(feed_config['api_link'], max_page)
    filtered_items = filter_items(items, feed_config['include_regex'], feed_config['exclude_regex'])
    
    update_rss_file(feed_config, filtered_items)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: rssfeed.py feed_number page_number")
        sys.exit(1)
    
    feed_number = int(sys.argv[1])
    max_page = int(sys.argv[2])
    
    main(feed_number, max_page)
