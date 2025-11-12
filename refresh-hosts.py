
import requests
import time
import json
import database
from datetime import datetime

# === SETTINGS ===
DETAIL_TIMEOUT = 10  # timeout for each IP's /api/tags

def fetch_models_from_ip(ip):
    """Queries a single IP for its Ollama models."""
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
    
    print("[+] Starting host refresh...", flush=True)
    hosts = database.get_all_hosts()
    
    for host in hosts:
        ip = host['ip_address']
        host_id = host['id']
        
        print(f"[+] Refreshing {ip}...", flush=True)
        detailed_models = fetch_models_from_ip(ip)
        
        if detailed_models:
            performance_guess = estimate_host_performance(detailed_models)
            print(f"  [>] Found {len(detailed_models)} models on {ip}", flush=True)
            print(f"  [i] Probable performance: {performance_guess}", flush=True)
            
            database.add_or_update_host(ip, performance_guess, is_alive=1) # Update last_seen and performance
            database.clear_models_for_host(host_id)
            database.add_models(host_id, detailed_models)
            print(f"  [✓] Host {ip} and its models updated in the database.", flush=True)
        else:
            print(f" [-] {ip} is unreachable or has no models. Marking as dead.", flush=True)
            database.mark_host_as_dead(host_id)
            
        time.sleep(1) # Be nice to the hosts
        
    print("\n[✓] Host refresh complete. Database is up to date.", flush=True)

if __name__ == "__main__":
    main()
