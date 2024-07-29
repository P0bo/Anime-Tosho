import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from pytz import timezone
import os

# File path
xml_file_path = 'Ember.xml'

# URL to fetch JSON data
json_url = "https://feed.animetosho.org/json?q=%22%5BEMBER%5D%22+-batch+-bd"

# Fetch JSON data
response = requests.get(json_url)
data = response.json()

# Function to convert Unix timestamp to RFC 822 format
def unix_to_rfc822(timestamp):
    dt = datetime.fromtimestamp(timestamp, tz=timezone('Asia/Kolkata'))
    return dt.strftime('%a, %d %b %Y %H:%M:%S +0530')

# Load existing XML file or create a new one
if os.path.exists(xml_file_path):
    tree = ET.parse(xml_file_path)
    root = tree.getroot()
else:
    root = ET.Element('rss', xmlns_atom="https://feed.animetosho.org/json?q=%22%5BEMBER%5D%22+-batch+-bd", version="2.0")
    channel = ET.SubElement(root, 'channel')
    ET.SubElement(channel, 'title').text = 'Ember'
    ET.SubElement(channel, 'link').text = 'https://nyaa.si/user/Ember_Encodes'
    tree = ET.ElementTree(root)

# Get the channel element
channel = root.find('channel')

# Track existing item links
existing_items = {item.find('guid').text for item in channel.findall('item')} if channel is not None else set()

# Add new items to the XML
for item in data:
    torrent_url = item.get('torrent_url', '')
    
    if torrent_url in existing_items:
        continue
    
    entry = ET.SubElement(channel, 'item')
    
    title = item.get('title', '')
    ET.SubElement(entry, 'title').text = title
    
    ET.SubElement(entry, 'link').text = torrent_url
    
    guid = ET.SubElement(entry, 'guid', isPermaLink="true")
    guid.text = torrent_url
    
    pubDate = unix_to_rfc822(item.get('timestamp', 0))
    ET.SubElement(entry, 'pubDate').text = pubDate
    
    description = f"{item.get('total_size', 0) / (1024 * 1024):.1f} MiB | Seeders: {item.get('seeders', 0)} | Leechers: {item.get('leechers', 0)} | AniDB: {item.get('anidb_aid', '')} | <a href=\"{item.get('link', '')}\">{item.get('title', '')}</a>"
    description_elem = ET.SubElement(entry, 'description')
    description_elem.text = f"<![CDATA[{description}]]>"

# Save updated XML file
tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)

print(f"RSS feed XML has been updated and saved as '{xml_file_path}'.")
