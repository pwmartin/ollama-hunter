# Ollama Hunter

**Ollama Hunter** is a Python toolset that discovers, analyzes, and serves information about publicly exposed Ollama LLM instances. It uses Shodan to find hosts, stores the data in a local SQLite database, and can expose this data via a local API.

This tool is designed for researchers and security analysts who want to map and monitor the exposure of open LLM endpoints on the internet.

---

## ✨ Features

-   **Shodan Scraping**: Finds hosts running Ollama on port `11434` using your Shodan session cookie.
-   **Database Storage**: Saves all discovered hosts and their models to a persistent SQLite database (`ollama_hosts.db`).
-   **Host Refresh**: Includes a script to periodically check the liveness of discovered hosts and update their model lists.
-   **API Service**: Provides a local Flask-based API to serve the collected data in JSON format.
-   **Detailed Analysis**: Estimates host performance based on the models they are running.

---

## 🚀 Setup and Usage

### 1. Environment Setup

It is recommended to run this project in a Python virtual environment.

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate
```

### 2. Installation

Install the required Python libraries using `pip`.

```bash
# Install dependencies
pip install -r requirements.txt
```

The core dependencies are `requests`, `beautifulsoup4`, and `Flask`.

### 3. Running the Scripts

**A. Initialize the Database**

Before running any other script, initialize the SQLite database:

```bash
python database.py
```

**B. Find New Hosts (`ollama-hunter.py`)**

This script scrapes Shodan for new Ollama instances and adds them to the database. It will prompt you to enter your Shodan `polito` cookie value.

```bash
# The script will prompt you for your Shodan cookie
python ollama-hunter.py
```

**C. Refresh Existing Hosts (`refresh-hosts.py`)**

This script iterates through the hosts in your database, checks if they are still online, and updates their model lists.

```bash
python refresh-hosts.py
```

**D. Run the Provider Service (`provider-service.py`)**

This script starts a local web service that exposes the collected data via an API.

```bash
python provider-service.py
```

The API will be available at `http://0.0.0.0:5000/api/providers`.

### Utility Scripts

**Interrogate a Single Host (`interrogate-host.py`)**

This script queries a single Ollama host and appends its model details to the `ollama_models_details.csv` file. *Note: This script has not been updated to use the database.*

```bash
python interrogate-host.py <IP_ADDRESS>
```

**Test a Model on a Host (`test-ollama-host.py`)**

This script sends a predefined prompt to a specific model on a remote Ollama host to test its functionality.

```bash
python test-ollama-host.py <IP_ADDRESS> <MODEL_NAME>
```