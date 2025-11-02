
import sqlite3
from datetime import datetime

DB_FILE = "ollama_hosts.db"

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def create_database():
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create hosts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hosts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT UNIQUE NOT NULL,
            country TEXT,
            last_seen TEXT NOT NULL,
            performance TEXT,
            is_alive INTEGER DEFAULT 1
        )
    ''')
    
    # Create models table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            modified_at TEXT,
            parameter_size TEXT,
            quantization_level TEXT,
            FOREIGN KEY (host_id) REFERENCES hosts (id)
        )
    ''')
    conn.commit()

def add_or_update_host(ip_address, performance, is_alive=1, country=None):
    """Adds a new host or updates the last_seen, performance, and is_alive status of an existing one."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    
    cursor.execute("SELECT id, country FROM hosts WHERE ip_address = ?", (ip_address,))
    host = cursor.fetchone()
    
    if host:
        # Update existing host
        host_id = host['id']
        # Don't overwrite an existing country with None
        if country is None:
            country = host['country']

        cursor.execute('''
            UPDATE hosts
            SET last_seen = ?, performance = ?, is_alive = ?, country = ?
            WHERE id = ?
        ''', (now, performance, is_alive, country, host_id))
    else:
        # Insert new host
        cursor.execute('''
            INSERT INTO hosts (ip_address, last_seen, performance, is_alive, country)
            VALUES (?, ?, ?, ?, ?)
        ''', (ip_address, now, performance, is_alive, country))
        host_id = cursor.lastrowid
        
    conn.commit()
    return host_id

def add_models(host_id, models):
    """Adds a list of models for a given host."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for model in models:
        cursor.execute('''
            INSERT INTO models (host_id, name, modified_at, parameter_size, quantization_level)
            VALUES (?, ?, ?, ?, ?)
        ''', (host_id, model['name'], model['modified_at'], model['parameter_size'], model['quantization_level']))
    conn.commit()

def get_all_hosts():
    """Retrieves all hosts from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosts")
    hosts = cursor.fetchall()
    return hosts

def get_host_by_ip(ip_address):
    """Retrieves a host by its IP address."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hosts WHERE ip_address = ?", (ip_address,))
    host = cursor.fetchone()
    return host

def mark_host_as_dead(host_id):
    """Marks a host as not alive."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE hosts SET is_alive = 0 WHERE id = ?", (host_id,))
    conn.commit()

def clear_models_for_host(host_id):
    """Clears all models for a given host."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM models WHERE host_id = ?", (host_id,))
    conn.commit()

if __name__ == '__main__':
    print("[+] Initializing database...")
    create_database()
    print("[✓] Database initialized successfully at", DB_FILE)
