import json
import feedparser
from datetime import datetime
from typing import List, Dict, Any, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.schema import BaseOutputParser
import os
from urllib.parse import urlparse, quote
import requests


def build_google_news_rss_url(topic: str, language: str = "en-US", country: str = "US") -> str:
    """
    Build a Google News RSS URL for a given search topic
    
    Args:
        topic: Search topic/query (e.g., "Harry Styles", "artificial intelligence")
        language: Language code (default: en-US)
        country: Country code (default: US)
        
    Returns:
        Google News RSS URL for the topic
    """
    # URL encode the search query
    encoded_topic = quote(topic)
    
    # Build the Google News RSS URL
    base_url = "https://news.google.com/rss/search"
    url = f"{base_url}?q={encoded_topic}&hl={language}&gl={country}&ceid={country}:{language.split('-')[0]}"
    
    return url

class ArticleCategorizer:
    """LangChain-powered agent for categorizing RSS articles into sections"""
    
    def __init__(self, google_api_key: str = None, model_name: str = "gemini-2.0-flash"):
        """
        Initialize the article categorizer
        
        Args:
            google_api_key: Google API key (can also be set via GOOGLE_API_KEY env var)
            model_name: Model to use for categorization (default: gemini-2.0-flash-exp)
        """
        if google_api_key:
            os.environ["GOOGLE_API_KEY"] = google_api_key
        elif not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("Google API key must be provided either as parameter or GOOGLE_API_KEY env var")
        
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.2)
        
        # Prompt for categorizing a small chunk of articles
        self.chunk_categorization_prompt = ChatPromptTemplate.from_template(
            """You are an expert media analyst. Analyze these articles and classify each one with media tier and coverage type.

Articles to classify:
{articles_text}

For each article, determine:
1. **Media Tier**: 
   - "top-tier": BBC, CNN, Reuters, Guardian, NYT, AP, Washington Post, NPR, ABC, CBS, NBC
   - "mid-tier": Regional newspapers, entertainment magazines, music publications, Sky, Independent, Mirror
   - "low-tier": Blogs, social media, unknown sources

2. **Coverage Type**:
   - "headline": Subject is main focus (in title/headline)  
   - "mention": Subject mentioned but not primary focus

CRITICAL: Respond with ONLY valid JSON array, no other text:
[
    {{
        "title": "Article title",
        "link": "original_url",
        "source": "Source name",
        "tier": "top-tier|mid-tier|low-tier", 
        "coverage_type": "headline|mention"
    }}
]

JSON only. No explanations or formatting."""
        )
        
        # Create the chain using the newer syntax
        self.chunk_categorization_chain = self.chunk_categorization_prompt | self.llm

    def fetch_rss_articles(self, rss_url: str, max_articles: int = 20) -> List[Dict[str, str]]:
        """
        Fetch articles from RSS feed with source detection
        
        Args:
            rss_url: URL of the RSS feed
            max_articles: Maximum number of articles to fetch
            
        Returns:
            List of articles with title, link, summary, and source
        """
        try:
            # Parse the RSS feed
            feed = feedparser.parse(rss_url)
            
            if feed.bozo:
                print(f"Warning: RSS feed may have issues: {feed.bozo_exception}")
            
            # Extract source info from feed
            feed_source = "Unknown Source"
            if hasattr(feed.feed, 'title'):
                feed_source = feed.feed.title
            elif hasattr(feed.feed, 'link'):
                parsed_url = urlparse(feed.feed.link)
                feed_source = parsed_url.netloc.replace('www.', '')
            
            articles = []
            for entry in feed.entries[:max_articles]:
                # Extract source from individual article if available
                article_source = feed_source
                if entry.get("link"):
                    try:
                        parsed_url = urlparse(entry.get("link"))
                        domain = parsed_url.netloc.replace('www.', '')
                        if domain:
                            article_source = domain
                    except:
                        pass
                
                article = {
                    "title": entry.get("title", "Untitled"),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", entry.get("description", "")),
                    "published": entry.get("published", ""),
                    "source": article_source
                }
                
                # Clean up the title and summary
                article["title"] = self._clean_text(article["title"])
                article["summary"] = self._clean_text(article["summary"])
                
                articles.append(article)
            
            print(f"Successfully fetched {len(articles)} articles from {feed_source}")
            return articles
            
        except Exception as e:
            raise Exception(f"Error fetching RSS feed {rss_url}: {str(e)}")

    def _clean_text(self, text: str) -> str:
        """Clean HTML tags and extra whitespace from text"""
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Clean up whitespace
        text = ' '.join(text.split())
        return text.strip()

    def categorize_articles(self, articles: List[Dict[str, str]], subject_override: str = None) -> Dict[str, Any]:
        """
        Categorize articles into sections using LangChain with chunked processing
        
        Args:
            articles: List of articles to categorize
            subject_override: Override the auto-generated subject
            
        Returns:
            JSON structure with categorized articles
        """
        if not articles:
            return {
                "subject": subject_override or f"News Summary - {datetime.now().strftime('%B %d, %Y')}",
                "sections": [],
                "filename": f"news-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"
            }
        
        # Process articles in chunks of 3
        chunk_size = 3
        all_categorized_articles = []
        
        print(f"Processing {len(articles)} articles in chunks of {chunk_size}...")
        
        for i in range(0, len(articles), chunk_size):
            chunk = articles[i:i + chunk_size]
            chunk_num = (i // chunk_size) + 1
            print(f"Processing chunk {chunk_num}/{(len(articles) + chunk_size - 1) // chunk_size} ({len(chunk)} articles)")
            
            try:
                # Prepare articles text for this chunk
                articles_text = ""
                for j, article in enumerate(chunk, 1):
                    articles_text += f"{j}. Title: {article['title']}\n"
                    articles_text += f"   URL: {article['link']}\n"
                    articles_text += f"   Source: {article.get('source', 'Unknown')}\n"
                    if article['summary']:
                        articles_text += f"   Summary: {article['summary'][:150]}...\n"
                    articles_text += "\n"
                
                # Get categorization from LangChain for this chunk
                result = self.chunk_categorization_chain.invoke({"articles_text": articles_text})
                
                # Extract content from the result
                if hasattr(result, 'content'):
                    result_text = result.content.strip()
                else:
                    result_text = str(result).strip()
                
                # Strip markdown code blocks if present
                if result_text.startswith('```json'):
                    result_text = result_text[7:]  # Remove ```json
                if result_text.startswith('```'):
                    result_text = result_text[3:]   # Remove ```
                if result_text.endswith('```'):
                    result_text = result_text[:-3]  # Remove closing ```
                result_text = result_text.strip()
                
                # Parse the JSON response
                chunk_results = json.loads(result_text)
                
                # Add the categorized articles to our collection
                if isinstance(chunk_results, list):
                    all_categorized_articles.extend(chunk_results)
                else:
                    print(f"Warning: Chunk {chunk_num} returned non-list result, skipping")
                    
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse JSON for chunk {chunk_num}: {e}")
                print(f"Raw response: {result_text}")
                # Skip this chunk and continue with others
                continue
            except Exception as e:
                print(f"Warning: Error processing chunk {chunk_num}: {e}")
                # Skip this chunk and continue with others
                continue
        
        print(f"Successfully categorized {len(all_categorized_articles)} articles")
        
        # Organize articles into sections by tier and coverage type
        sections = self._organize_articles_into_sections(all_categorized_articles)
        
        return {
            "subject": subject_override or f"News Summary - {datetime.now().strftime('%B %d, %Y')}",
            "sections": sections,
            "filename": f"news-report-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"
        }

    def _organize_articles_into_sections(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Organize categorized articles into sections by tier and coverage type
        
        Args:
            articles: List of categorized articles with tier and coverage_type
            
        Returns:
            List of sections with headings and items
        """
        # Group articles by tier and coverage type
        grouped = {
            "top-tier": {"headline": [], "mention": []},
            "mid-tier": {"headline": [], "mention": []},
            "low-tier": {"headline": [], "mention": []}
        }
        
        for article in articles:
            tier = article.get("tier", "low-tier")
            coverage_type = article.get("coverage_type", "mention")
            
            if tier in grouped and coverage_type in grouped[tier]:
                grouped[tier][coverage_type].append(article)
        
        # Build sections in priority order
        sections = []
        
        # Top-tier headlines (highest priority)
        if grouped["top-tier"]["headline"]:
            sections.append({
                "heading": "Top-Tier Headlines",
                "items": grouped["top-tier"]["headline"]
            })
        
        # Top-tier mentions
        if grouped["top-tier"]["mention"]:
            sections.append({
                "heading": "Top-Tier Mentions",
                "items": grouped["top-tier"]["mention"]
            })
        
        # Mid-tier headlines
        if grouped["mid-tier"]["headline"]:
            sections.append({
                "heading": "Mid-Tier Headlines", 
                "items": grouped["mid-tier"]["headline"]
            })
        
        # Mid-tier mentions  
        if grouped["mid-tier"]["mention"]:
            sections.append({
                "heading": "Mid-Tier Coverage",
                "items": grouped["mid-tier"]["mention"]
            })
        
        # Low-tier combined (if any)
        low_tier_items = grouped["low-tier"]["headline"] + grouped["low-tier"]["mention"]
        if low_tier_items:
            sections.append({
                "heading": "Other Coverage",
                "items": low_tier_items
            })
        
        # Fallback if no sections created
        if not sections and articles:
            sections = [{
                "heading": "News Updates",
                "items": articles
            }]
        
        return sections

    def process_rss_to_json(self, rss_url: str, max_articles: int = 20, subject_override: str = None) -> Dict[str, Any]:
        """
        Complete pipeline: fetch RSS -> categorize -> return JSON
        
        Args:
            rss_url: RSS feed URL
            max_articles: Maximum articles to process
            subject_override: Custom subject line
            
        Returns:
            JSON structure ready for report generation
        """
        print(f"Fetching articles from: {rss_url}")
        articles = self.fetch_rss_articles(rss_url, max_articles)
        print(f"Fetched {len(articles)} articles")
        
        print("Categorizing articles...")
        categorized_data = self.categorize_articles(articles, subject_override)
        print(f"Created {len(categorized_data['sections'])} sections")
        
        return categorized_data

    def process_topic_to_json(self, topic: str, max_articles: int = 20, subject_override: str = None, 
                             language: str = "en-US", country: str = "US") -> Dict[str, Any]:
        """
        Complete pipeline: topic -> build RSS URL -> fetch -> categorize -> return JSON
        
        Args:
            topic: Search topic (e.g., "Harry Styles", "artificial intelligence")
            max_articles: Maximum articles to process
            subject_override: Custom subject line (defaults to "{topic} News Summary")
            language: Language code (default: en-US)
            country: Country code (default: US)
            
        Returns:
            JSON structure ready for report generation
        """
        # Build RSS URL from topic
        rss_url = build_google_news_rss_url(topic, language, country)
        print(f"Built RSS URL for topic '{topic}': {rss_url}")
        
        # Set default subject if not provided
        if subject_override is None:
            subject_override = f"{topic} News Summary"
        
        # Use existing RSS processing
        return self.process_rss_to_json(rss_url, max_articles, subject_override)

    def save_json(self, data: Dict[str, Any], output_path: str) -> str:
        """Save categorized data to JSON file"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return output_path


def create_report_from_rss(rss_url: str = None, max_articles: int = 30, subject_override: str = None, 
                          output_json: str = None, output_pdf: str = None, 
                          google_api_key: str = None) -> tuple[str, str]:
    """
    High-level function to create a report from RSS feed (writes to disk)
    
    Args:
        rss_url: RSS feed URL
        max_articles: Maximum articles to process
        subject_override: Custom subject line
        output_json: Output path for JSON file
        output_pdf: Output path for PDF file
        google_api_key: Google API key
        
    Returns:
        Tuple of (json_path, pdf_path)
    """
    from report_generator import generate_report_pdf
    
    # Initialize the agent
    agent = ArticleCategorizer(google_api_key)
    
    # Process RSS to JSON
    data = agent.process_rss_to_json(rss_url, max_articles, subject_override)
    
    # Save JSON
    if not output_json:
        output_json = f"rss-data-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    json_path = agent.save_json(data, output_json)
    
    # Generate PDF
    if not output_pdf:
        output_pdf = data["filename"]
    
    pdf_bytes = generate_report_pdf(
        subject=data["subject"],
        sections=data["sections"]
    )
    
    with open(output_pdf, 'wb') as f:
        f.write(pdf_bytes)
    
    return json_path, output_pdf


def create_report_from_topic(topic: str, max_articles: int = 30, subject_override: str = None, 
                            output_json: str = None, output_pdf: str = None, 
                            google_api_key: str = None, language: str = "en-US", 
                            country: str = "US") -> tuple[str, str]:
    """
    High-level function to create a report from a search topic (writes to disk)
    
    Args:
        topic: Search topic (e.g., "Harry Styles", "artificial intelligence")
        max_articles: Maximum articles to process
        subject_override: Custom subject line (defaults to "{topic} News Summary")
        output_json: Output path for JSON file
        output_pdf: Output path for PDF file
        google_api_key: Google API key
        language: Language code (default: en-US)
        country: Country code (default: US)
        
    Returns:
        Tuple of (json_path, pdf_path)
    """
    from report_generator import generate_report_pdf
    
    # Initialize the agent
    agent = ArticleCategorizer(google_api_key)
    
    # Process topic to JSON
    data = agent.process_topic_to_json(topic, max_articles, subject_override, language, country)
    
    # Save JSON
    if not output_json:
        output_json = f"rss-data-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    json_path = agent.save_json(data, output_json)
    
    # Generate PDF
    if not output_pdf:
        output_pdf = data["filename"]
    
    pdf_bytes = generate_report_pdf(
        subject=data["subject"],
        sections=data["sections"]
    )
    
    with open(output_pdf, 'wb') as f:
        f.write(pdf_bytes)
    
    return json_path, output_pdf


def create_report_from_topic_memory(topic: str, max_articles: int = 30, subject_override: str = None,
                                   google_api_key: str = None, language: str = "en-US", 
                                   country: str = "US") -> tuple[dict, bytes]:
    """
    In-memory function to create a report from a search topic (Cloud Run compatible)
    
    Args:
        topic: Search topic (e.g., "Harry Styles", "artificial intelligence")
        max_articles: Maximum articles to process
        subject_override: Custom subject line (defaults to "{topic} News Summary")
        google_api_key: Google API key
        language: Language code (default: en-US)
        country: Country code (default: US)
        
    Returns:
        Tuple of (json_data_dict, pdf_bytes)
    """
    from report_generator import generate_report_pdf
    
    # Initialize the agent
    agent = ArticleCategorizer(google_api_key)
    
    # Process topic to JSON (in memory)
    data = agent.process_topic_to_json(topic, max_articles, subject_override, language, country)
    
    # Generate PDF (in memory)
    pdf_bytes = generate_report_pdf(
        subject=data["subject"],
        sections=data["sections"]
    )
    
    return data, pdf_bytes


if __name__ == "__main__":
    # Example usage
    import sys
    
    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY environment variable")
        print("You can get an API key from: https://aistudio.google.com/app/apikey")
        sys.exit(1)
    
    print("RSS to Report Generator Demo")
    print("=" * 40)
    
    # Default topic
    topic = "Harry Styles"
    print(f"Processing topic: '{topic}'")
    
    # Build and show the RSS URL
    rss_url = build_google_news_rss_url(topic)
    print(f"RSS URL: {rss_url}")
    
    try:
        json_path, pdf_path = create_report_from_topic(
            topic=topic,
            max_articles=15,
            subject_override=f"{topic} News Summary"
        )
        
        print(f"✅ Success!")
        print(f"📄 JSON saved: {json_path}")
        print(f"📄 PDF saved: {pdf_path}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1) 