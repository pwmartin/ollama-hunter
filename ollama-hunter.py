
import requests
from bs4 import BeautifulSoup
import time
import json
import database

# === USER INPUT ===
polito_cookie = input("Enter your Shodan 'polito' cookie value: ").strip()

# === SETTINGS ===
BASE_URL = "https://www.shodan.io/search"
QUERY = 'port:11434 product:"Ollama" country:"US"'
START_PAGE = 1
DELAY = 2  # seconds between page fetches
DETAIL_TIMEOUT = 10  # timeout for each IP's /api/tags

# === HEADERS ===
HEADERS = {
    "Host": "www.shodan.io",
    "Cookie": f'polito="{polito_cookie}"',
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.100 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.shodan.io/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# === REST OF THE SCRIPT ===
def scrape_hosts_from_page(page):
    params = {
        "query": QUERY,
        "page": page
    }

    print(f"[+] Fetching Shodan page {page}...")
    response = requests.get(BASE_URL, headers=HEADERS, params=params)

    if response.status_code != 200:
        print(f"[!] Error: Status code {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results = soup.find_all("div", class_="result")

    hosts = []
    for result in results:
        a_tag = result.find("a", class_="title", href=True)
        country_span = result.find("span", class_="country_name")
        
        if a_tag and "/host/" in a_tag["href"]:
            ip = a_tag["href"].split("/host/")[1]
            country = country_span.text.strip() if country_span else None
            hosts.append({"ip": ip, "country": country})

    return hosts

def fetch_models_from_ip(ip):
    url = f"http://{ip}:11434/api/tags"
    try:
        res = requests.get(url, timeout=DETAIL_TIMEOUT)
        res.raise_for_status()
        data = res.json()
        
        detailed_models = []
        for m in data.get("models", []):
            details = m.get("details", {})
            detailed_models.append({
                "name": m.get("name"),
                "modified_at": m.get("modified_at"),
                "parameter_size": details.get("parameter_size"),
                "quantization_level": details.get("quantization_level"),
            })
        return detailed_models
    except (requests.RequestException, json.JSONDecodeError) as e:
        return None

def parse_size_to_gb(size_str):
    """Converts a model size string (e.g., '7B', '750M') to a float in GB."""
    if not isinstance(size_str, str):
        return 0.0
    size_str = size_str.lower().strip()
    try:
        if 'b' in size_str:
            return float(size_str.replace('b', ''))
        if 'm' in size_str:
            return float(size_str.replace('m', '')) / 1000
    except (ValueError, TypeError):
        return 0.0
    return 0.0

def estimate_host_performance(detailed_models):
    """Analyzes model details to make an educated guess about host performance."""
    if not detailed_models:
        return "Unknown"

    max_param_size_gb = 0
    has_unquantized_large_model = False
    all_heavily_quantized = True
    
    # Quantization levels from best to worst
    high_quality_quants = {'F16', 'BF16', 'Q8_0', 'Q6_K'}
    low_quality_quants = {'Q4_0', 'Q4_K_M', 'Q3_K_S', 'Q2_K'}

    for model in detailed_models:
        param_size_gb = parse_size_to_gb(model.get("parameter_size"))
        if param_size_gb > max_param_size_gb:
            max_param_size_gb = param_size_gb

        quant_level = model.get("quantization_level", "unknown")
        
        # Check for unquantized large models
        if param_size_gb > 25 and quant_level in high_quality_quants:
            has_unquantized_large_model = True

        # Check if any model is NOT heavily quantized
        if quant_level not in low_quality_quants and not quant_level.startswith('IQ'):
            all_heavily_quantized = False

    if has_unquantized_large_model or max_param_size_gb > 60:
        return "High-Performance"
    
    if max_param_size_gb > 25:
        return "Mid-Range"

    if max_param_size_gb > 10 and all_heavily_quantized:
        return "CPU-Only / Low-RAM"

    if max_param_size_gb < 10:
        return "Small-Model / Hobbyist"

    return "Mid-Range" # Default for intermediate cases

def main():
    database.create_database() # Ensure db is created
    processed_ips = set()

    try:
        page = START_PAGE
        while True:
            hosts = scrape_hosts_from_page(page)
            if not hosts:
                print("[*] No more results found. Stopping.")
                break

            for host_data in hosts:
                ip = host_data['ip']
                country = host_data['country']

                if ip in processed_ips:
                    continue
                
                processed_ips.add(ip)

                print(f"[+] Checking {ip} ({country or 'Unknown Country'})...")
                detailed_models = fetch_models_from_ip(ip)

                if detailed_models:
                    performance_guess = estimate_host_performance(detailed_models)
                    print(f"  [>] Found {len(detailed_models)} models on {ip}")
                    print(f"  [i] Probable performance: {performance_guess}")

                    host_id = database.add_or_update_host(ip, performance_guess, is_alive=1, country=country)
                    database.clear_models_for_host(host_id)
                    database.add_models(host_id, detailed_models)
                    print(f"  [✓] Host {ip} and its models saved to the database.")

                else:
                    print(f" [-] {ip} has no models or is unreachable.")
                    host = database.get_host_by_ip(ip)
                    if host:
                        database.mark_host_as_dead(host['id'])
                        print(f"  [!] Marked host {ip} as dead in the database.")

                time.sleep(1)

            page += 1
            time.sleep(DELAY)

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.")

    print(f"\n[✓] Done. Database is up to date.")

if __name__ == "__main__":
    main()
