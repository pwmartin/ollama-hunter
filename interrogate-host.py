#!/usr/bin/env python3

import requests
import argparse
import csv
import json
import os

# === SETTINGS ===
DETAIL_TIMEOUT = 15  # timeout for the IP's /api/tags endpoint

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
        print(f"[!] Error querying {ip}: {e}")
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
    
    high_quality_quants = {'F16', 'BF16', 'Q8_0', 'Q6_K'}
    low_quality_quants = {'Q4_0', 'Q4_K_M', 'Q3_K_S', 'Q2_K'}

    for model in detailed_models:
        param_size_gb = parse_size_to_gb(model.get("parameter_size"))
        if param_size_gb > max_param_size_gb:
            max_param_size_gb = param_size_gb

        quant_level = model.get("quantization_level", "unknown")
        
        if param_size_gb > 25 and quant_level in high_quality_quants:
            has_unquantized_large_model = True

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

    return "Mid-Range"

def main():
    parser = argparse.ArgumentParser(
        description="Interrogate a single Ollama host and append its model details to a CSV.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("host", help="IP address or hostname of the Ollama server.")
    args = parser.parse_args()

    csv_output_file = "ollama_models_details.csv"
    
    print(f"[+] Checking {args.host}...")
    detailed_models = fetch_models_from_ip(args.host)

    if detailed_models:
        print(f"  [>] Found {len(detailed_models)} models on {args.host}")
        performance_guess = estimate_host_performance(detailed_models)
        print(f"  [i] Probable performance: {performance_guess}")

        # Check if file exists to determine if we need to write a header
        file_exists = os.path.isfile(csv_output_file)

        with open(csv_output_file, "a", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["ip_address", "model_name", "parameter_size", "quantization_level", "modified_at", "probable_performance"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()
            
            for model in detailed_models:
                writer.writerow({
                    "ip_address": args.host,
                    "probable_performance": performance_guess,
                    "model_name": model["name"],
                    "parameter_size": model["parameter_size"],
                    "quantization_level": model["quantization_level"],
                    "modified_at": model["modified_at"],
                })
        
        print(f"\n[✓] Done. Results for {args.host} appended to: {csv_output_file}")
    else:
        print(f" [-] {args.host} has no models or is unreachable.")

if __name__ == "__main__":
    main()