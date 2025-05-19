# Steve AI OS MCP Server

A Model Context Protocol (MCP) server that allows AI agents to interact with the available features in Steve. The server implements a hybrid approach, using direct MongoDB queries for read operations and API calls for write operations.

## Current supported tools

- List User Products
- Get User Tasks
- Create Task
- Check Authentication

## Installation

### Prerequisites

- Python 3.10+
- Poetry (for dependency management)

### Setup

1. Clone the repository and install dependencies:
   ```bash
   git clone https://github.com/Walturn-LLC/steve-mcp.git
   cd steve-mcp
   poetry install
   ```

2. Configure environment in `.env`:
   ```
   DEBUG=false
   MONGODB_URL=mongodb://localhost:27017
   DATABASE_NAME=steve
   STEVE_API_TOKEN=your_api_token
   MCP_SERVER_PORT=3000
   ```

## Usage

### Authentication

This MCP server is designed to work with the Steve MCP client for authentication. For testing with Claude Desktop or other hosts:

1. Generate a Firebase access token for the Steve API
2. Add it to `.env` as `STEVE_API_TOKEN`
3. For development, set `DEBUG=true` to use a default token (not for production)

### Running the Server

```bash
# For development (HTTP server)
poetry run python server.py

# For Claude Desktop (stdio transport)
./run_steve_mcp.sh
```

### Claude Desktop Configuration

Add to your `claude_desktop_config.json`:
```json
{
  "mcps": [
    {
      "name": "Steve Tasks",
      "command": "/bin/bash",
      "args": ["/path/to/run_steve_mcp.sh"]
    }
  ]
}
```

## Environment Variables

- `DEBUG`: Enable debug mode (true/false)
- `MONGODB_URL`: MongoDB connection string
- `DATABASE_NAME`: MongoDB database name
- `STEVE_API_TOKEN`: Authentication token for API requests
- `MCP_SERVER_PORT`: Port for running the MCP server
- `CLAUDE_DESKTOP_MCP`: Set to 1 when running for Claude Desktop

## License

[MIT License](LICENSE)