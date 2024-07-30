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
    # Check if any ID field (nyaa_id, nyaa_subdom, tosho_id, anidex_id) matches
    for existing_item in existing_items:
        if any(existing_item.find(id_type) is not None and existing_item.find(id_type).text == str(item.get(id_type)) for id_type in ['nyaa_id', 'nyaa_subdom', 'tosho_id', 'anidex_id']):
            return True
    return False

def create_cdata_element(tag, text):
    element = ET.Element(tag)
    element.text = text
    return element

def create_rss(feed_config, items):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    
    title_element = ET.Element("title")
    title_element.text = feed_config['name']
    channel.append(title_element)
    
    link_element = ET.Element("link")
    link_element.text = feed_config['link']
    channel.append(link_element)
    
    for item in items:
        item_element = ET.Element("item")
        
        title_element = create_cdata_element("title", item['title'])
        item_element.append(title_element)
        
        link_element = ET.Element("link")
        link_element.text = item['torrent_url']
        item_element.append(link_element)
        
        guid_element = ET.Element("guid")
        guid_element.text = item['torrent_url']
        item_element.append(guid_element)
        
        id_types = ['nyaa_id', 'nyaa_subdom', 'tosho_id', 'anidex_id']
        for id_type in id_types:
            if id_type in item and item[id_type]:
                id_element = ET.Element(id_type)
                id_element.text = str(item[id_type])
                item_element.append(id_element)
                break
        
        pubDate_element = ET.Element("pubDate")
        pubDate_element.text = datetime.utcfromtimestamp(item['timestamp']).strftime('%a, %d %b %Y %H:%M:%S +0000')
        item_element.append(pubDate_element)
        
        description_text = f"{item['total_size'] // (1024 * 1024)} MiB | Seeders: {item['seeders']} | Leechers: {item['leechers']} | AniDB: {item['anidb_aid']} | <a href=\"{item['link']}\">{item['title']}</a>"
        description_element = create_cdata_element("description", description_text)
        item_element.append(description_element)
        
        channel.append(item_element)
    
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
        
        title_element = ET.Element("title")
        title_element.text = feed_config['name']
        channel.append(title_element)
        
        link_element = ET.Element("link")
        link_element.text = feed_config['link']
        channel.append(link_element)
        
        existing_items = []
    
    for item in new_items:
        if not item_exists(existing_items, item):
            item_element = ET.Element("item")
            
            title_element = create_cdata_element("title", item['title'])
            item_element.append(title_element)
            
            link_element = ET.Element("link")
            link_element.text = item['torrent_url']
            item_element.append(link_element)
            
            guid_element = ET.Element("guid")
            guid_element.text = item['torrent_url']
            item_element.append(guid_element)
            
            id_types = ['nyaa_id', 'nyaa_subdom', 'tosho_id', 'anidex_id']
            for id_type in id_types:
                if id_type in item and item[id_type]:
                    id_element = ET.Element(id_type)
                    id_element.text = str(item[id_type])
                    item_element.append(id_element)
                    break
            
            pubDate_element = ET.Element("pubDate")
            pubDate_element.text = datetime.utcfromtimestamp(item['timestamp']).strftime('%a, %d %b %Y %H:%M:%S +0000')
            item_element.append(pubDate_element)
            
            description_text = f"{item['total_size'] // (1024 * 1024)} MiB | Seeders: {item['seeders']} | Leechers: {item['leechers']} | AniDB: {item['anidb_aid']} | <a href=\"{item['link']}\">{item['title']}</a>"
            description_element = create_cdata_element("description", description_text)
            item_element.append(description_element)
            
            channel.insert(0, item_element)  # Insert at the top
    
    # Convert the ElementTree to a string
    xml_str = ET.tostring(root, encoding="utf-8", method="xml")

    # Pretty print the XML string
    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

    # Remove extra blank lines between elements
    pretty_xml_str = "\n".join(line for line in pretty_xml_str.splitlines() if line.strip())

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
