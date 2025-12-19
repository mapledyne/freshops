# FreshOps

A Python library and CLI tool for interacting with the FreshService API.

## Installation

### Library Only

```bash
pip install freshops
```

### Library + CLI

```bash
pip install freshops[cli]
```

### Development

```bash
pip install -e ".[dev,cli]"
```

## Configuration

Set the following environment variables or create a `.env` file:

```bash
FRESHSERVICE_DOMAIN=yourcompany
FRESHSERVICE_API_KEY=your_api_key_here
```

**Note:** Use just the company name for the domain, not the full URL.
For example, if your FreshService URL is `https://evergreen.freshservice.com`, 
set `FRESHSERVICE_DOMAIN=evergreen`.

## Usage as a Library

```python
from freshops import FreshServiceClient, load_config

# Load config from environment/.env
config = load_config()
client = FreshServiceClient(config)
agents = client.list_agents()

# Or create client directly with credentials
client = FreshServiceClient.from_credentials(
    domain="company.freshservice.com",
    api_key="your_api_key"
)
```

## Usage as CLI

**Note:** CLI features require installing with the `[cli]` extra:
```bash
pip install freshops[cli]
```

### Tickets

```bash
# List recent tickets
freshops tickets list

# List tickets with filters
freshops tickets list --status open --priority high

# Get a specific ticket
freshops tickets get 12345
```

### Agents

```bash
# List all agents
freshops agents list
```

### Requesters

```bash
# List requesters
freshops requesters list

# Search requesters by email
freshops requesters search --email "user@example.com"
```

### Assets

```bash
# List assets
freshops assets list

# Search assets
freshops assets search --name "laptop"
```

## Logging

Set `FRESHOPS_LOG_LEVEL` environment variable to control verbosity:
- `DEBUG` - Detailed API call information
- `INFO` - General operation info (default)
- `WARNING` - Warnings only
- `ERROR` - Errors only

## Development

```bash
# Install with dev and CLI dependencies
pip install -e ".[dev,cli]"

# Run tests
pytest

# Run linter
ruff check src/

# Run type checker
mypy src/
```
