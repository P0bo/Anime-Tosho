import requests
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from xml.dom import minidom
import re
import os

def fetch_feed_data(api_link, page_number):
    data = []
    for page in range(1, page_number + 1):
        response = requests.get(f"{api_link}{page}")
        if response.status_code == 200:
            page_data = response.json()
            data.extend(page_data)
        else:
            print(f"Failed to fetch data for page {page}")
    return data

def parse_data(data, include_regex, exclude_regex):
    filtered_data = []
    include_pattern = re.compile(include_regex) if include_regex else None
    exclude_pattern = re.compile(exclude_regex) if exclude_regex else None

    for item in data:
        title = item.get("title", "")
        if include_pattern and not include_pattern.search(title):
            continue
        if exclude_pattern and exclude_pattern.search(title):
            continue

        filtered_data.append(item)
    return filtered_data

def create_or_update_rss(feed_config, feed_data):
    rss_dir = 'rssfeed'
    if not os.path.exists(rss_dir):
        os.makedirs(rss_dir)

    xml_file_path = os.path.join(rss_dir, feed_config["xml_file_name"])
    root = ET.Element("rss", version="2.0")
    channel = ET.SubElement(root, "channel")
    ET.SubElement(channel, "title").text = feed_config["name"]
    ET.SubElement(channel, "link").text = feed_config["link"]

    existing_ids = set()
    if os.path.exists(xml_file_path):
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        for item in root.find("channel").findall("item"):
            nyaa_id = item.find("nyaa_id")
            if nyaa_id is not None:
                existing_ids.add(nyaa_id.text)
            else:
                tosho_id = item.find("tosho_id")
                if tosho_id is not None:
                    existing_ids.add(tosho_id.text)
                else:
                    anidex_id = item.find("anidex_id")
                    if anidex_id is not None:
                        existing_ids.add(anidex_id.text)

    for item in feed_data:
        entry_id = item.get("nyaa_id") or item.get("tosho_id") or item.get("anidex_id")
        if entry_id in existing_ids:
            continue

        feed_item = ET.SubElement(channel, "item")
        title = ET.SubElement(feed_item, "title")
        title.text = f"<![CDATA[{item['title']}]]>"
        ET.SubElement(feed_item, "link").text = item["link"]
        guid = ET.SubElement(feed_item, "guid")
        guid.text = item["link"]
        ET.SubElement(feed_item, "nyaa_id").text = item.get("nyaa_id", "")
        pub_date = datetime.utcfromtimestamp(item["timestamp"]).strftime('%a, %d %b %Y %H:%M:%S +0000')
        ET.SubElement(feed_item, "pubDate").text = pub_date
        description = ET.SubElement(feed_item, "description")
        description.text = f"<![CDATA[{item['description']}]]>"

    xml_str = ET.tostring(root, encoding="utf-8", method="xml")
    pretty_xml_str = minidom.parseString(xml_str).toprettyxml(indent="  ")
    pretty_xml_str = "\n".join(line for line in pretty_xml_str.splitlines() if line.strip())
    pretty_xml_str = pretty_xml_str.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')

    with open(xml_file_path, "w", encoding="utf-8") as f:
        f.write(pretty_xml_str)

def main():
    with open('config.json', 'r') as f:
        config = json.load(f)

    import sys
    if len(sys.argv) != 3:
        print("Usage: rssfeed.py feed_number page_number")
        return

    feed_number = int(sys.argv[1])
    page_number = int(sys.argv[2])

    feed_config = None
    for feed in config["feeds"]:
        if feed["number"] == feed_number:
            feed_config = feed
            break

    if not feed_config:
        print(f"No feed configuration found for feed number {feed_number}")
        return

    feed_data = fetch_feed_data(feed_config["api_link"], page_number)
    parsed_data = parse_data(feed_data, feed_config["include_regex"], feed_config["exclude_regex"])
    create_or_update_rss(feed_config, parsed_data)

if __name__ == "__main__":
    main()
