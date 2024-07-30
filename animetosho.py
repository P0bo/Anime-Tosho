import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz
from xml.dom import minidom
import json
import re
import sys
import os
import html

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

# Create 'feeds' directory if it doesn't exist
os.makedirs('feeds', exist_ok=True)

# Load existing XML if it exists, otherwise create a new XML structure
def load_or_create_xml(feed):
    xml_file_path = os.path.join('feeds', feed["xml_file_name"])
    try:
        print(f"Loading XML file: {xml_file_path}")  # Debug print
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
    except FileNotFoundError:
        root = ET.Element("rss", version="2.0")
        channel = ET.SubElement(root, "channel")
        title = ET.SubElement(channel, "title")
        title.text = feed["name"]
        link = ET.SubElement(channel, "link")
        link.text = feed["link"]  # Use link for channel
        tree = ET.ElementTree(root)
    except ET.ParseError as e:
        print(f"Error parsing XML file {xml_file_path}: {e}")  # Debug print
        raise  # Re-raise the exception after printing the debug info
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

# Function to filter titles based on include and exclude regex
def is_valid_title(title, include_regex, exclude_regex):
    if include_regex:
        include_pattern = re.compile(include_regex, re.IGNORECASE)
        if not include_pattern.search(title):
            return False
    if exclude_regex:
        exclude_pattern = re.compile(exclude_regex, re.IGNORECASE)
        if exclude_pattern.search(title):
            return False
    return True

# Function to update XML with new items
def update_xml_with_data(channel, data, include_regex, exclude_regex):
    for entry in data:
        if not item_exists(channel, entry["title"]) and is_valid_title(entry["title"], include_regex, exclude_regex):
            item = ET.SubElement(channel, "item")
            
            title = ET.SubElement(item, "title")
            title.text = html.escape(entry["title"])  # Escape special characters
            
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
            hyperlink = f'<a href="https://nyaa.si/view/{entry["nyaa_id"]}">{html.escape(entry["title"])}</a>'
            description_text = f"<![CDATA[{size} | Seeders: {seeders} | Leechers: {leechers} | AniDB: {anidb} | {hyperlink}]]>"

            description = ET.Element("description")
            description.text = description_text
            item.append(description)

# Function to sort items based on pubDate
def sort_items_by_date(channel):
    items = channel.findall("item")
    items.sort(key=lambda item: datetime.strptime(item.find("pubDate").text, "%a, %d %b %Y %H:%M:%S %z"), reverse=True)
    
    # Remove all items and re-add them in sorted order
    for item in channel.findall("item"):
        channel.remove(item)
        
    for item in items:
        channel.append(item)

# Main function to process pages
def process_feed(feed, start_page):
    print(f"Processing feed: {feed['name']}")  # Debug print
    root, tree = load_or_create_xml(feed)
    channel = get_channel_element(root)
    
    page_number = start_page
    while page_number >= 1:
        print(f"Fetching data from page {page_number} for {feed['name']}...")
        data = fetch_data_from_page(feed["api_link"], page_number)
        update_xml_with_data(channel, data, feed.get("include_regex"), feed.get("exclude_regex"))
        page_number -= 1

    # Sort items by publication date before saving
    sort_items_by_date(channel)

    # Convert the ElementTree to a string
    xml_str = ET.tostring(root, encoding="utf-8", method="xml")

    # Pretty print the XML string
    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")

    # Remove extra blank lines between elements
    pretty_xml_str = "\n".join(line for line in pretty_xml_str.splitlines() if line.strip())

    # Fix CDATA section being escaped
    pretty_xml_str = pretty_xml_str.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

    # Save the pretty printed XML to the file
    xml_file_path = os.path.join('feeds', feed["xml_file_name"])
    with open(xml_file_path, "w", encoding="utf-8") as f:
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
    for feed_no in feeds.keys():
        feed = feeds.get(feed_no)
        if feed:
            print(f"Updating feed number {feed_no}")
            process_feed(feed, start_page)
        else:
            print(f"Feed number {feed_no} not found.")
else:
    feed = feeds.get(feed_no)
    if feed:
        process_feed(feed, start_page)
    else:
        print(f"Feed number {feed_no} not found.")
