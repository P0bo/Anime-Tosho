import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz
from xml.dom import minidom
import sys
import re

# Function to convert timestamp to RFC822 format
def timestamp_to_rfc822(timestamp):
    dt = datetime.fromtimestamp(timestamp, pytz.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")

# Function to fetch JSON data from a specific page
def fetch_data_from_page(page_number):
    url = f"https://feed.animetosho.org/json?q=%22%5BEmber%5D%22+-batch+-bd&page={page_number}"
    response = requests.get(url)
    return response.json()

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

# Function to filter titles
def is_valid_title(title):
    # Regular expression to match titles with S#E# pattern
    pattern = re.compile(r'\bS\d{1,4}E\d{1,4}\b', re.IGNORECASE)
    return bool(pattern.search(title))

# Function to update XML with new items
def update_xml_with_data(data):
    for entry in data:
        if not item_exists(entry["title"]) and is_valid_title(entry["title"]):
            item = ET.SubElement(channel, "item")
            
            title = ET.SubElement(item, "title")
            title.text = entry["title"]
            
            link = ET.SubElement(item, "link")
            link.text = entry["torrent_url"]
            
            guid = ET.SubElement(item, "guid", isPermaLink="true")
            guid.text = entry["torrent_url"]
            
            pubDate = ET.SubElement(item, "pubDate")
            pubDate.text = timestamp_to_rfc822(entry["timestamp"])
            
            # Create the description content manually
            size = f"{entry['total_size'] / (1024 * 1024):.1f} MiB"
            seeders = entry["seeders"]
            leechers = entry["leechers"]
            anidb = entry["anidb_aid"]
            hyperlink = f'<a href="https://nyaa.si/view/{entry["nyaa_id"]}">{entry["title"]}</a>'
            description_text = f"<![CDATA[{size} | Seeders: {seeders} | Leechers: {leechers} | AniDB: {anidb} | {hyperlink}]]>"

            # Directly set the description text without escaping
            description = ET.Element("description")
            description.text = description_text
            item.append(description)

# Main function to process pages
def process_pages(start_page):
    page_number = start_page
    while page_number >= 1:
        print(f"Fetching data from page {page_number}...")
        data = fetch_data_from_page(page_number)
        update_xml_with_data(data)
        page_number -= 1

# Check if a page number was provided as an argument
if len(sys.argv) > 1:
    try:
        start_page = int(sys.argv[1])
    except ValueError:
        start_page = 1
else:
    start_page = 1

# Process pages starting from the specified page number
process_pages(start_page)

# Convert the ElementTree to a string
xml_str = ET.tostring(root, encoding="utf-8", method="xml")

# Pretty print the XML string
pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

# Fix CDATA section being escaped
pretty_xml_str = pretty_xml_str.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

# Save the pretty printed XML to the file
with open("Ember.xml", "w", encoding="utf-8") as f:
    f.write(pretty_xml_str)
