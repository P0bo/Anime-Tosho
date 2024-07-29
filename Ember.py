import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz

# Function to convert timestamp to RFC822 format
def timestamp_to_rfc822(timestamp):
    dt = datetime.fromtimestamp(timestamp, pytz.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")

# Fetch the JSON data from the URL
url = "https://feed.animetosho.org/json?q=%22%5BEMBER%5D%22+-batch+-bd"
response = requests.get(url)
data = response.json()

# Load existing XML if it exists, otherwise create a new XML structure
try:
    tree = ET.parse("Ember.xml")
    root = tree.getroot()
except FileNotFoundError:
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    title = ET.SubElement(channel, "title")
    title.text = "Ember"
    link = ET.SubElement(channel, "link")
    link.text = "https://nyaa.si/user/Ember_Encodes"
    tree = ET.ElementTree(root)

# Get the channel element
channel = root.find("channel")

# Function to check if item already exists in the XML
def item_exists(title):
    for item in channel.findall("item"):
        if item.find("title").text == title:
            return True
    return False

# Iterate over the JSON data and add new items to the XML
for entry in data:
    if not item_exists(entry["title"]):
        item = ET.SubElement(channel, "item")
        
        title = ET.SubElement(item, "title")
        title.text = entry["title"]
        
        link = ET.SubElement(item, "link")
        link.text = entry["torrent_url"]
        
        guid = ET.SubElement(item, "guid", isPermaLink="true")
        guid.text = entry["torrent_url"]
        
        pubDate = ET.SubElement(item, "pubDate")
        pubDate.text = timestamp_to_rfc822(entry["timestamp"])
        
        description = ET.SubElement(item, "description")
        hyperlink = f'<a href="https://nyaa.si/view/{entry["nyaa_id"]}">#{entry["nyaa_id"]} | {entry["title"]}</a>'
        description.text = f"<![CDATA[{hyperlink}]]>"

# Save the updated XML to the file
tree.write("Ember.xml", encoding="utf-8", xml_declaration=True)
