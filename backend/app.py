from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json
import time
from dotenv import load_dotenv

from scrapy.crawler import CrawlerRunner
from scrapy.utils.project import get_project_settings
from scrapy.signalmanager import dispatcher
from scrapy import signals
from scrapy.utils.log import configure_logging
from crochet import setup, run_in_reactor

from scraper.scraper.spiders.my_spider import MySpider

load_dotenv()

# Initialize Flask and CORS
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Scrapy environment
setup()  
configure_logging()
runner = CrawlerRunner(get_project_settings())  

# scraped data
scraped_data = []

# Handle item scraped from spider
def crawler_results(signal, sender, item, response, spider):
    scraped_data.append(dict(item))

# Connect Scrapy 
dispatcher.connect(crawler_results, signal=signals.item_scraped)

# Run Scrapy spider
@run_in_reactor
def run_scrapy_spider(url):
    global scraped_data
    scraped_data.clear()
    return runner.crawl(MySpider, url=url)

# Groq API to summarize
def generate_summary(scraped_data, language, wordCount):
    url = "https://api.groq.com/openai/v1/chat/completions"
    api_key = os.getenv('API_KEY')
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
        
    }

    payload = {
        "model": "llama-3.3-70b-versatile", 
        "messages": [{
            "role": "user",
            "content": (
                f"Summarize the following content in {language} around {wordCount} words, adapting to its type: "
                "News Article → Headline + key takeaways\n"
                "Research Paper → Abstract + key conclusions\n"
                "Legal Document → Important clauses only\n"
                "Blog Post → Key insights + action points\n"
                "Code Documentation → Functionality overview + key methods\n"
                "YouTube Video Transcript → Short script summary\n"
                "Technical Report → Summary of findings + key recommendations\n"
                "Product Review → Pros, cons, and final verdict\n"
                "Interview/Podcast Transcript → Key quotes + major discussion points\n"
                "Social Media Post/Tweet Thread → Condensed key ideas\n"
                "Use numbered points where necessary. If no summary is possible, state so. Ensure the summary starts with the main topic.\n\n"
                f"{scraped_data}"
            )
        }]
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json().get('choices', [{}])[0].get('message', {}).get('content', "❌ Failed to generate summary.")
    else:
        return f"❌ Failed to generate summary. Status: {response.status_code}"

# API endpoint for scraping and summarizing
@app.route('/scrape', methods=['POST'])
def scrape_website():
    print("📩 Received a request at /scrape")
    data = request.get_json()
    # print(f"📝 Request data: {data}")

    url = data.get('url')
    language = data.get('language', 'English')
    wordCount = data.get('wordCount', '150')

    if not url:
        return jsonify({"error": "❌ URL is required"}), 400

    print(f"🔗 Starting Scrapy spider for URL: {url}")
    run_scrapy_spider(url)  

    print("⏳ Waiting for spider to finish (approx. 5 seconds)...")
    time.sleep(5)  

    if not scraped_data:
        return jsonify({
            "message": "⚠️ No data was scraped from the website.",
            "data": [],
            "summary": ""
        }), 400

    print("🧠 Generating summary ...")
    summary = generate_summary(scraped_data, language, wordCount)

    return jsonify({
        "message": "✅ Scraping and summarization completed successfully.",
        "data": scraped_data,
        "summary": summary
    }), 200

# Invoke server
if __name__ == '__main__':
    print("✅ Flask Server Started 🚀")
    app.run(port=8001, debug=True)
