import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz
from xml.dom import minidom
import json
import re
import sys

# Function to convert timestamp to RFC822 format
def timestamp_to_rfc822(timestamp):
    dt = datetime.fromtimestamp(timestamp, pytz.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S %z")

# Function to fetch JSON data from a specific page
def fetch_data_from_page(api_link, page_number):
    url = f"{api_link}{page_number}"
    response = requests.get(url)
    return response.json()

# Function to load configuration from JSON file
def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

# Load feeds configuration
config = load_config()
feeds = {feed["number"]: feed for feed in config["feeds"]}

# Load existing XML if it exists, otherwise create a new XML structure
def load_or_create_xml(feed):
    try:
        tree = ET.parse(feed["xml_file_name"])
        root = tree.getroot()
    except FileNotFoundError:
        root = ET.Element("rss", version="2.0")
        channel = ET.SubElement(root, "channel")
        title = ET.SubElement(channel, "title")
        title.text = feed["name"]
        link = ET.SubElement(channel, "link")
        link.text = feed["link"]  # Use link for channel
        tree = ET.ElementTree(root)
    return root, tree

# Get the channel element
def get_channel_element(root):
    return root.find("channel")

# Function to check if item already exists in the XML
def item_exists(channel, title):
    for item in channel.findall("item"):
        if item.find("title").text == title:
            return True
    return False

# Function to filter titles
def is_valid_title(title, filter_regex):
    pattern = re.compile(filter_regex, re.IGNORECASE)
    return bool(pattern.search(title))

# Function to update XML with new items
def update_xml_with_data(channel, data, filter_regex):
    for entry in data:
        if not item_exists(channel, entry["title"]) and (not filter_regex or is_valid_title(entry["title"], filter_regex)):
            item = ET.SubElement(channel, "item")
            
            title = ET.SubElement(item, "title")
            title.text = entry["title"]
            
            link = ET.SubElement(item, "link")
            link.text = entry["torrent_url"]
            
            guid = ET.SubElement(item, "guid", isPermaLink="true")
            guid.text = entry["torrent_url"]
            
            pubDate = ET.SubElement(item, "pubDate")
            pubDate.text = timestamp_to_rfc822(entry["timestamp"])
            
            size = f"{entry['total_size'] / (1024 * 1024):.1f} MiB"
            seeders = entry["seeders"]
            leechers = entry["leechers"]
            anidb = entry["anidb_aid"]
            hyperlink = f'<a href="https://nyaa.si/view/{entry["nyaa_id"]}">{entry["title"]}</a>'
            description_text = f"<![CDATA[{size} | Seeders: {seeders} | Leechers: {leechers} | AniDB: {anidb} | {hyperlink}]]>"

            description = ET.Element("description")
            description.text = description_text
            item.append(description)

# Main function to process pages
def process_feed(feed, start_page):
    root, tree = load_or_create_xml(feed)
    channel = get_channel_element(root)
    
    page_number = start_page
    while page_number >= 1:
        print(f"Fetching data from page {page_number} for {feed['name']}...")
        data = fetch_data_from_page(feed["api_link"], page_number)
        update_xml_with_data(channel, data, feed["filter"])
        page_number -= 1

    # Convert the ElementTree to a string
    xml_str = ET.tostring(root, encoding="utf-8", method="xml")

    # Pretty print the XML string
    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

    # Fix CDATA section being escaped
    pretty_xml_str = pretty_xml_str.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

    # Save the pretty printed XML to the file
    with open(feed["xml_file_name"], "w", encoding="utf-8") as f:
        f.write(pretty_xml_str)

# Check if a page number was provided as an argument
if len(sys.argv) > 1:
    try:
        feed_no = int(sys.argv[1])
        start_page = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    except ValueError:
        feed_no = 0
        start_page = 1
else:
    feed_no = 0
    start_page = 1

# Process specified feed or all feeds
if feed_no == 0:
    for feed in feeds.values():
        process_feed(feed, start_page)
else:
    feed = feeds.get(feed_no)
    if feed:
        process_feed(feed, start_page)
    else:
        print(f"Feed number {feed_no} not found.")
