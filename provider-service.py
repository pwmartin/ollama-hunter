
from flask import Flask, jsonify, render_template, redirect, url_for, request, flash
import database
import subprocess
import sys

app = Flask(__name__)
app.secret_key = 'supersecretkey' # Needed for flashing messages

@app.route("/run-hunter", methods=["POST"])
def run_hunter():
    """Triggers the ollama-hunter.py script as a background process."""
    cookie = request.form.get('shodan-cookie')
    if not cookie:
        flash("Shodan cookie is required!", "error")
        return redirect(url_for('index'))

    try:
        # Use Popen to run the script in the background
        # We pass the python executable from the current environment
        python_executable = sys.executable
        subprocess.Popen([python_executable, "ollama-hunter.py", "--cookie", cookie])
        flash("Ollama Hunter process started in the background. Refresh the page in a few moments to see results.", "success")
    except Exception as e:
        flash(f"Failed to start Ollama Hunter: {e}", "error")
    
    return redirect(url_for('index'))

@app.route("/run-refresh", methods=["POST"])
def run_refresh():
    """Triggers the refresh-hosts.py script as a background process."""
    try:
        python_executable = sys.executable
        subprocess.Popen([python_executable, "refresh-hosts.py"])
        flash("Host refresh process started in the background. Refresh the page in a few moments to see results.", "success")
    except Exception as e:
        flash(f"Failed to start host refresh: {e}", "error")

    return redirect(url_for('index'))


@app.route("/", methods=["GET"])
def index():
    """Renders the web UI for displaying live hosts with sorting and filtering."""
    conn = database.get_db_connection()
    cursor = conn.cursor()

    # Get filter and sort parameters from URL
    selected_models = request.args.getlist('models')
    sort_by = request.args.get('sort_by', 'last_seen') # Default to last_seen

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
        query += " ORDER BY CASE performance WHEN 'High-Performance' THEN 1 WHEN 'Mid-Range' THEN 2 WHEN 'CPU-Only / Low-RAM' THEN 3 WHEN 'Small-Model / Hobbyist' THEN 4 ELSE 5 END ASC"
    else: # Default to last_seen
        query += " ORDER BY last_seen DESC"

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
        sort_by=sort_by
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

if __name__ == "__main__":
    database.create_database() # Ensure database is initialized
    app.run(debug=True, host='0.0.0.0', port=5000)
