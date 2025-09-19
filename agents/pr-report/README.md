# PR Report Coral Agent

A specialized Coral agent that generates comprehensive news reports from RSS feeds and various topics. This agent integrates with the Coral framework to provide structured news analysis and categorization services.

## Features

- **News Report Generation**: Create comprehensive reports from search topics using Google News RSS feeds
- **RSS Feed Processing**: Fetch and categorize articles from specific RSS URLs
- **Article Categorization**: Automatically categorize articles by:
  - Media tier (top-tier, mid-tier, low-tier)
  - Coverage type (headline vs mention)
- **PDF Generation & Upload**: Automatically generates PDF reports and uploads them to Google Cloud Storage
- **Public URL Access**: Returns public URLs for generated PDF reports
- **Multi-language Support**: Support for different languages and countries
- **Coral Integration**: Full integration with Coral framework for inter-agent communication

## Tools Available

### `generate_news_report`
Generate a comprehensive news report from RSS feeds for a given topic and upload PDF to GCP.
- **topic**: The search topic (e.g., "artificial intelligence", "climate change")
- **max_articles**: Maximum number of articles to process (default: 20)
- **subject_override**: Custom subject line for the report
- **language**: Language code (default: en-US)
- **country**: Country code (default: US)
- **Returns**: JSON with categorized data, PDF URL, and upload status

### `fetch_rss_articles`
Fetch and categorize articles from a specific RSS feed URL and upload PDF to GCP.
- **rss_url**: The RSS feed URL to fetch articles from
- **max_articles**: Maximum number of articles to fetch (default: 20)
- **Returns**: JSON with categorized data, PDF URL, and upload status

### `build_google_news_url`
Build a Google News RSS URL for a given search topic.
- **topic**: The search topic
- **language**: Language code (default: en-US)
- **country**: Country code (default: US)

## Configuration

The agent requires the following environment variables:

### Required
- `GOOGLE_API_KEY`: Google API key for Gemini AI model
- `CORAL_SSE_URL`: Coral server URL for SSE connection
- `CORAL_AGENT_ID`: Unique agent identifier
- `GCP_BUCKET_NAME`: GCP Cloud Storage bucket name for PDF uploads

### Optional (with defaults)
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to GCP service account JSON file (optional if using default credentials)
- `MODEL_NAME`: Model to use (default: "gemini-2.0-flash")
- `MODEL_PROVIDER`: Model provider (default: "google_genai")
- `MODEL_MAX_TOKENS`: Max tokens (default: "16000")
- `MODEL_TEMPERATURE`: Model temperature (default: "0.3")
- `TIMEOUT_MS`: Connection timeout in milliseconds (default: "300")

## Usage

### Running the Agent

```bash
# Using the run script
./run_agent.sh

# Or directly with uv
uv run main.py
```

### Docker

```bash
# Build the image
docker build -t pr-report-agent .

# Run the container
docker run -e GOOGLE_API_KEY=your_key -e CORAL_SSE_URL=your_url -e GCP_BUCKET_NAME=your_bucket pr-report-agent
```

## GCP Setup

To enable PDF upload functionality:

1. **Create a GCS Bucket**:
   ```bash
   gsutil mb gs://your-bucket-name
   gsutil iam ch allUsers:objectViewer gs://your-bucket-name
   ```

2. **Set up Authentication**:
   - **Option A**: Use service account key file
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
     ```
   - **Option B**: Use default credentials (if running on GCP)

3. **Configure Environment**:
   ```bash
   export GCP_BUCKET_NAME="your-bucket-name"
   ```

## Agent Behavior

The agent operates in a continuous loop:

1. **Wait for Mentions**: Listens for mentions from other agents via Coral's `wait_for_mentions`
2. **Process Requests**: Analyzes incoming requests to determine the appropriate news processing action
3. **Execute Tools**: Uses specialized tools to generate reports, fetch RSS articles, or build URLs
4. **Respond**: Sends structured results back to the requesting agent via `send_message`
5. **Error Handling**: Provides helpful error information when processing fails

## Media Tier Classification

The agent categorizes news sources into three tiers:

- **Top-tier**: BBC, CNN, Reuters, Guardian, NYT, AP, Washington Post, NPR, ABC, CBS, NBC
- **Mid-tier**: Regional newspapers, entertainment magazines, music publications, Sky, Independent, Mirror
- **Low-tier**: Blogs, social media, unknown sources

## Coverage Type Classification

- **Headline**: Subject is the main focus (appears in title/headline)
- **Mention**: Subject is mentioned but not the primary focus

## Dependencies

- LangChain ecosystem for AI/ML capabilities
- Google Generative AI for article categorization
- feedparser for RSS feed processing
- Coral MCP adapters for framework integration

## Development

To set up for development:

```bash
# Install dependencies
uv sync

# Run in development mode
uv run python main.py
```

## Integration with Coral

This agent is designed to work seamlessly within the Coral ecosystem, communicating with other agents through the standard Coral messaging protocol. It can be called by other agents to provide news analysis and reporting capabilities.
