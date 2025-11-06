# Multi Agent Demo

> [!TIP]
> Updated for Coral Server v1

## Prerequisites

```bash
./check-dependencies.sh
```

This script will automatically check for valid versions of all prerequisites.

## Running Coral Server

First, make sure you have pulled the coral-server submodule:
```bash
git submodule init
git submodule update
```

Now, we can cd into the coral-server folder, and start it.

```bash
cd coral-server
REGISTRY_FILE_PATH="../registry.toml" ./gradlew run
```

> [!NOTE]
> We use the `REGISTRY_FILE_PATH` environment variable to tell Coral Server where our custom `registry.toml` is.

## Running Coral Studio

```bash
npx @coral-protocol/coral-studio
```

We can then visit Coral Studio at [http://localhost:3000/](http://localhost:3000/)

# What next?
Check out our [docs](https://docs.coralprotocol.org/) for more information on how Coral Studio works, how to write agents that work with Coral, and using Coral in your applications.


# Quickstart
### Creating a session

Coral instantiates ephemeral agents inside sessions. To create a session, you can use the following code:

```
export OPENAI_API_KEY="your_openai_api_key"
```

```
export FIRECRAWL_API_KEY="your_firecrawl_api_key"
```

```
export GITHUB_PAT="your_github_pat"
```


```
curl 
```
Note: You can also create sessions via the Coral Studio UI. You can import the json portion of the above command to jumpstart the form

### Explanation
The Coral server provides a REST API for creating and managing multi-agent sessions. 
