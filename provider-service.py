
from flask import Flask, jsonify, render_template
import database

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    """Renders the web UI for displaying live hosts."""
    conn = database.get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, ip_address, country, last_seen, performance FROM hosts WHERE is_alive = 1 ORDER BY last_seen DESC")
    hosts = cursor.fetchall()
    
    hosts_with_models = []
    for host in hosts:
        host_data = dict(host)
        
        cursor.execute("SELECT name, parameter_size, quantization_level FROM models WHERE host_id = ?", (host['id'],))
        models = cursor.fetchall()
        
        host_data["models"] = [dict(model) for model in models]
        hosts_with_models.append(host_data)
        
    conn.close()
    return render_template("index.html", hosts=hosts_with_models)

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
