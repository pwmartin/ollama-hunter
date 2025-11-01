#!/usr/bin/env python3

import requests
import argparse
import time
import json

def test_remote_model(host, model_name):
    """
    Sends a predefined prompt to a remote Ollama model and prints the response.

    Args:
        host (str): The IP address or hostname of the Ollama server.
        model_name (str): The name of the model to test (e.g., 'llama3:latest').
    """
    url = f"http://{host}:11434/api/generate"
    prompt = '''
Please perform the following sequence of tasks exactly as specified:

1.  **Role-play:** Adopt the persona of a helpful robot assistant from the year 2300. In this persona, briefly introduce yourself.
2.  **Reasoning:** Solve this simple logic riddle: "I have cities, but no houses. I have mountains, but no trees. I have water, but no fish. What am I?"
3.  **Code Generation:** Write a Python function named `find_even_numbers` that takes a list of integers as input and returns a new list containing only the even numbers.
4.  **Creative Writing:** Compose a four-line poem (AABB rhyme scheme) about a cat looking at the moon.
5.  **Strict Formatting:** Format your *entire* response as a single, valid JSON object. Use the following exact keys for your answers: "introduction", "riddle_solution", "code_snippet", and "poem".
    '''
    
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False  # Wait for the full response
    }

    print(f"[*] Sending prompt to model '{model_name}' on host '{host}'...")
    print(f"[*] Prompt: \"{prompt}\"")
    
    try:
        start_time = time.monotonic()
        response = requests.post(url, json=payload, timeout=60)
        end_time = time.monotonic()
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        try:
            data = response.json()
            model_response = data.get("response", "No 'response' key found in JSON.")
            total_request_time = end_time - start_time
            
            print("\n" + "="*50)
            print(f"[+] Response from {model_name}:")
            print("="*50)
            print(model_response.strip())
            print("="*50)
            
            # Calculate and display performance metrics
            eval_count = data.get("eval_count")
            eval_duration_ns = data.get("eval_duration")

            print("\n" + "-"*50)
            print("[i] Performance Metrics:")
            print(f"    - Total response time: {total_request_time:.2f} seconds")
            if eval_count is not None and eval_duration_ns is not None and eval_duration_ns > 0:
                eval_duration_s = eval_duration_ns / 1_000_000_000
                tokens_per_second = eval_count / eval_duration_s
                print(f"    - Tokens generated: {eval_count}")
                print(f"    - Tokens per second: {tokens_per_second:.2f} t/s")
            else:
                print("    - Performance metrics (t/s) not available in response.")
            print("-"*50)

        except json.JSONDecodeError:
            print("\n[!] Error: Failed to decode JSON response from the server.")
            print(f"    Raw response: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"\n[!] Error connecting to {host}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Test a remote Ollama model with a predefined prompt.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("host", help="IP address or hostname of the Ollama server.")
    parser.add_argument("model", help="Name of the model to test (e.g., 'llama3:latest').")
    
    args = parser.parse_args()
    
    test_remote_model(args.host, args.model)

if __name__ == "__main__":
    main()