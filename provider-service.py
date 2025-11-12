
from flask import Flask, jsonify, render_template, redirect, url_for, request, flash, Response
import database
import subprocess
import sys

app = Flask(__name__)
app.secret_key = 'supersecretkey' # Needed for flashing messages

@app.route("/run-compass", methods=["POST"])
def run_compass():
    """Triggers the ollama-compass.py script as a background process."""
    cookie = request.form.get('shodan-cookie')
    if not cookie:
        flash("Shodan cookie is required!", "error")
        return redirect(url_for('index'))

    try:
        # Use Popen to run the script in the background
        # We pass the python executable from the current environment
        python_executable = sys.executable
        subprocess.Popen([python_executable, "ollama-compass.py", "--cookie", cookie])
        flash("Ollama Compass process started in the background. Refresh the page in a few moments to see results.", "success")
    except Exception as e:
        flash(f"Failed to start Ollama Compass: {e}", "error")
    
    return redirect(url_for('index'))

@app.route("/run-refresh", methods=["POST"])
def run_refresh():
    """Triggers the refresh-hosts.py script as a background process."""
    try:
        python_executable = sys.executable
        subprocess.Popen([python_executable, "refresh-hosts.py"])
    except Exception as e:
        flash(f"Failed to start host refresh: {e}", "error")

    return redirect(url_for('index'))


@app.route("/stream-refresh")
def stream_refresh():
    """Runs the refresh-hosts.py script and streams its output."""
    def generate():
        python_executable = sys.executable
        process = subprocess.Popen(
            [python_executable, "refresh-hosts.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        for line in process.stdout:
            yield f"data: {line}\n\n"
        process.wait()
        yield "data: __END__\n\n"
    return Response(generate(), mimetype='text/event-stream')


@app.route("/", methods=["GET"])
def index():
    """Renders the web UI for displaying live hosts with sorting and filtering."""
    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Get filter and sort parameters from URL
    selected_models = request.args.getlist('models')
    sort_by = request.args.get('sort_by', 'last_seen') # Default to last_seen
    order = request.args.get('order', 'desc')
    if order not in ['asc', 'desc']:
        order = 'desc'

    # Fetch all unique models for the filter dropdown
    cursor.execute("SELECT DISTINCT name FROM models ORDER BY name ASC")
    all_models = [row['name'] for row in cursor.fetchall()]

    # Base query
    query = "SELECT id, ip_address, country, last_seen, performance FROM hosts WHERE is_alive = 1"
    params = []

    # Add filtering by model
    if selected_models:
        query += " AND id IN (SELECT host_id FROM models WHERE name IN ({seq}))".format(
            seq=','.join(['?' for _ in selected_models]))
        params.extend(selected_models)

    # Add sorting
    if sort_by == 'performance':
        query += f" ORDER BY CASE performance WHEN 'High-Performance' THEN 1 WHEN 'Mid-Range' THEN 2 WHEN 'CPU-Only / Low-RAM' THEN 3 WHEN 'Small-Model / Hobbyist' THEN 4 ELSE 5 END {order}"
    else: # Default to last_seen
        query += f" ORDER BY last_seen {order}"

    cursor.execute(query, params)
    hosts = cursor.fetchall()
    
    hosts_with_models = []
    for host in hosts:
        host_data = dict(host)
        cursor.execute("SELECT name, parameter_size, quantization_level FROM models WHERE host_id = ?", (host['id'],))
        models = cursor.fetchall()
        host_data["models"] = [dict(model) for model in models]
        hosts_with_models.append(host_data)
        
    conn.close()
    return render_template(
        "index.html", 
        hosts=hosts_with_models, 
        all_models=all_models, 
        selected_models=selected_models,
        sort_by=sort_by,
        order=order
    )

@app.route("/api/providers", methods=["GET"])
def get_providers():
    """Returns a list of live Ollama hosts and their models."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    # Fetch live hosts
    cursor.execute("SELECT id, ip_address, country, last_seen, performance FROM hosts WHERE is_alive = 1")
    hosts = cursor.fetchall()
    
    providers = []
    for host in hosts:
        host_data = dict(host) # Convert Row object to dictionary
        
        # Fetch models for each host
        cursor.execute("SELECT name, modified_at, parameter_size, quantization_level FROM models WHERE host_id = ?", (host['id'],))
        models = cursor.fetchall()
        
        host_data["models"] = [dict(model) for model in models] # Convert Row objects to dictionaries
        providers.append(host_data)
        
    conn.close()
    return jsonify(providers)

import requests

@app.route("/api/host/<ip_address>/status", methods=["GET"])
def get_host_status(ip_address):
    """
    Acts as a proxy to query a remote host's /api/ps endpoint.
    This is necessary to avoid browser CORS issues.
    """
    url = f"http://{ip_address}:11434/api/ps"
    try:
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        return jsonify(res.json())
    except requests.RequestException as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    database.create_database() # Ensure database is initialized
    # Check for FLASK_ENV environment variable to determine debug mode
    import os
    debug_mode = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
