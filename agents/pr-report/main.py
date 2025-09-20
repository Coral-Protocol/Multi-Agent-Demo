import urllib.parse
from dotenv import load_dotenv
import os, json, asyncio, traceback
from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.tools import tool
from typing import Dict, Any, List, Optional
from rss_agent import ArticleCategorizer, build_google_news_rss_url, create_report_from_topic_memory
from gcp_storage import upload_report_to_gcs


@tool
def generate_news_report(
    topic: str,
    max_articles: int = 20,
    subject_override: str = None,
    language: str = "en-US",
    country: str = "US"
) -> Dict[str, Any]:
    """
    Generate a comprehensive news report from RSS feeds for a given topic and upload PDF to GCP.
    
    Args:
        topic: The search topic (e.g., "artificial intelligence", "climate change")
        max_articles: Maximum number of articles to process (default: 20)
        subject_override: Custom subject line for the report
        language: Language code (default: en-US)
        country: Country code (default: US)
        
    Returns:
        Dictionary containing the categorized news report data and PDF URL
    """
    try:
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            return {"error": "GOOGLE_API_KEY environment variable not set"}
        
        # Generate the report
        data, pdf_bytes = create_report_from_topic_memory(
            topic=topic,
            max_articles=max_articles,
            subject_override=subject_override,
            google_api_key=google_api_key,
            language=language,
            country=country
        )
        
        # Upload PDF to GCP Storage
        bucket_name = os.getenv("GCP_BUCKET_NAME")
        if bucket_name:
            upload_result = upload_report_to_gcs(
                pdf_bytes=pdf_bytes,
                topic=topic,
                sections_count=len(data.get('sections', [])),
                bucket_name=bucket_name
            )
            
            if upload_result.get('success'):
                pdf_url = upload_result.get('pdf_url')
                upload_info = {
                    'pdf_uploaded': True,
                    'pdf_url': pdf_url,
                    'bucket_name': upload_result.get('bucket_name'),
                    'filename': upload_result.get('filename')
                }
            else:
                upload_info = {
                    'pdf_uploaded': False,
                    'upload_error': upload_result.get('error'),
                    'pdf_url': None
                }
        else:
            upload_info = {
                'pdf_uploaded': False,
                'upload_error': "GCP_BUCKET_NAME not configured",
                'pdf_url': None
            }
        print(f"Upload info: {upload_info}")
        return {
            "success": True,
            "data": data,
            "pdf_size": len(pdf_bytes),
            "message": f"Successfully generated report for '{topic}' with {len(data.get('sections', []))} sections",
            **upload_info
        }
    except Exception as e:
        return {"error": f"Failed to generate news report: {str(e)}"}


@tool
def fetch_rss_articles(
    rss_url: str,
    max_articles: int = 20
) -> Dict[str, Any]:
    """
    Fetch and categorize articles from a specific RSS feed URL and upload PDF to GCP.
    
    Args:
        rss_url: The RSS feed URL to fetch articles from
        max_articles: Maximum number of articles to fetch (default: 20)
        
    Returns:
        Dictionary containing the fetched and categorized articles and PDF URL
    """
    try:
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            return {"error": "GOOGLE_API_KEY environment variable not set"}
        
        # Process RSS feed
        agent = ArticleCategorizer(google_api_key)
        data = agent.process_rss_to_json(rss_url, max_articles)
        
        # Generate PDF from the data
        from report_generator import generate_report_pdf
        pdf_bytes = generate_report_pdf(
            subject=data["subject"],
            sections=data["sections"]
        )
        
        # Upload PDF to GCP Storage
        bucket_name = os.getenv("GCP_BUCKET_NAME")
        if bucket_name:
            # Extract topic from RSS URL for filename
            from urllib.parse import urlparse
            parsed_url = urlparse(rss_url)
            topic = parsed_url.netloc.replace('www.', '') or "rss-feed"
            
            upload_result = upload_report_to_gcs(
                pdf_bytes=pdf_bytes,
                topic=topic,
                sections_count=len(data.get('sections', [])),
                bucket_name=bucket_name
            )
            
            if upload_result.get('success'):
                upload_info = {
                    'pdf_uploaded': True,
                    'pdf_url': upload_result.get('pdf_url'),
                    'bucket_name': upload_result.get('bucket_name'),
                    'filename': upload_result.get('filename')
                }
            else:
                upload_info = {
                    'pdf_uploaded': False,
                    'upload_error': upload_result.get('error'),
                    'pdf_url': None
                }
        else:
            upload_info = {
                'pdf_uploaded': False,
                'upload_error': "GCP_BUCKET_NAME not configured",
                'pdf_url': None
            }
        print(f"Upload info: {upload_info}")
        return {
            "success": True,
            "data": data,
            "pdf_size": len(pdf_bytes),
            "message": f"Successfully fetched {len(data.get('sections', []))} sections from RSS feed",
            **upload_info
        }
    except Exception as e:
        return {"error": f"Failed to fetch RSS articles: {str(e)}"}


@tool
def build_google_news_url(
    topic: str,
    language: str = "en-US",
    country: str = "US"
) -> Dict[str, str]:
    """
    Build a Google News RSS URL for a given search topic.
    
    Args:
        topic: The search topic
        language: Language code (default: en-US)
        country: Country code (default: US)
        
    Returns:
        Dictionary containing the built RSS URL
    """
    try:
        url = build_google_news_rss_url(topic, language, country)
        return {
            "success": True,
            "url": url,
            "topic": topic,
            "message": f"Built RSS URL for topic '{topic}'"
        }
    except Exception as e:
        return {"error": f"Failed to build Google News URL: {str(e)}"}


def get_tools_description(tools):
    return "\n".join(
        f"Tool: {tool.name}, Schema: {json.dumps(tool.args).replace('{', '{{').replace('}', '}}')}"
        for tool in tools
    )


async def create_agent(coral_tools, agent_tools):
    coral_tools_description = get_tools_description(coral_tools)
    agent_tools_description = get_tools_description(agent_tools)
    combined_tools = coral_tools + agent_tools
    
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"""You are a PR Report agent that specializes in generating comprehensive news reports from RSS feeds and various topics. 
            Your primary capabilities include:
            
            1. Generating news reports from search topics using Google News RSS feeds.
               Note: Please describe each bit of information returned in the tool calls you make in the assistant message for your own note-taking, as you will forget the tool call results otherwise.
            2. Fetching and categorizing articles from specific RSS URLs
            3. Building Google News RSS URLs for any topic
            4. Categorizing news articles by media tier (top-tier, mid-tier, low-tier) and coverage type (headline vs mention)
            
            Follow these steps when interacting with other agents:
            1. Call wait_for_mentions from coral tools (timeoutMs: 30000) to receive mentions from other agents.
            2. When you receive a mention, keep the thread ID and the sender ID.
            3. Analyze the content to understand what type of news report or RSS processing is requested.
            4. Use your specialized tools to process the request:
               - generate_news_report: For creating comprehensive reports from search topics
               - fetch_rss_articles: For processing specific RSS feed URLs
               - build_google_news_url: For creating Google News RSS URLs
            5. Process the request using the most appropriate tool based on the instruction.
            6. Take the JSON result from your tool and format it as a clear, structured response.
            7. Use `send_message` from coral tools to send the JSON results back to the sender in the same thread with the processed data including the url of the PDF report. If a URL for the PDF is present then remove any errors or warnings.
            8. If any error occurs, use `send_message` to send error information and suggestions back to the sender.
            9. Always respond back to the sender agent with either results or error information.
            10. Wait for 2 seconds and repeat the process from step 1.

            Available Coral tools: {coral_tools_description}
            Available Agent tools: {agent_tools_description}
            
            When sending responses, include the complete JSON structure with sections, categorization, and metadata so other agents can process the news data effectively."""
        ),
        ("human", "Start the agent and wait for mentions from other agents."),
        ("placeholder", "{agent_scratchpad}")
    ])

    model = init_chat_model(
        model=os.getenv("MODEL_NAME", "gemini-2.0-flash"),
        model_provider=os.getenv("MODEL_PROVIDER", "google"),
        api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.3")),
        max_tokens=int(os.getenv("MODEL_MAX_TOKENS", "16000"))
    )
    
    agent = create_tool_calling_agent(model, combined_tools, prompt)
    return AgentExecutor(agent=agent, tools=combined_tools, verbose=True, handle_parsing_errors=True)


async def main():
    runtime = os.getenv("CORAL_ORCHESTRATION_RUNTIME", None)
    if runtime is None:
        load_dotenv()

    base_url = os.getenv("CORAL_SSE_URL")
    agentID = os.getenv("CORAL_AGENT_ID")

    coral_params = {
        "agentId": agentID,
        "agentDescription": "PR Report agent specializes in generating comprehensive news reports from RSS feeds, categorizing articles by media tier and coverage type, and processing various news sources for structured analysis."
    }

    query_string = urllib.parse.urlencode(coral_params)
    CORAL_SERVER_URL = f"{base_url}?{query_string}"
    print(f"Connecting to Coral Server: {CORAL_SERVER_URL}")

    timeout = float(os.getenv("TIMEOUT_MS", "300"))
    client = MultiServerMCPClient(
        connections={
            "coral": {
                "transport": "sse",
                "url": CORAL_SERVER_URL,
                "timeout": timeout,
                "sse_read_timeout": timeout,
            }
        }
    )

    print("Multi Server Connection Initialized")

    coral_tools = await client.get_tools(server_name="coral")
    
    # Define our custom agent tools
    agent_tools = [generate_news_report, fetch_rss_articles, build_google_news_url]
    
    print(f"Coral tools count: {len(coral_tools)}, Agent tools count: {len(agent_tools)}")

    agent_executor = await create_agent(coral_tools, agent_tools)

    while True:
        try:
            print("Starting new agent invocation")
            await agent_executor.ainvoke({"agent_scratchpad": []})
            print("Completed agent invocation, restarting loop")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Error in agent loop: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
