from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)  # This allows your frontend to talk to your backend



# Database configuration
DATABASE = 'crm.db'

def get_db_connection():
    """Create a connection to the database"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # This lets us access columns by name
    return conn

def init_db():
    """Initialize the database with tables if they don't exist"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create contacts table
    c.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            company TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create deals table
    c.execute('''
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL,
            deal_name TEXT NOT NULL,
            value REAL NOT NULL,
            stage TEXT DEFAULT 'qualification',
            status TEXT DEFAULT 'open',
            probability INTEGER DEFAULT 0,
            lead_source TEXT,
            budget TEXT,
            authority TEXT,
            need TEXT,
            timeline TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            FOREIGN KEY (contact_id) REFERENCES contacts(id)
        )
    ''')
    
    # Create activities table
    c.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deal_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deal_id) REFERENCES deals(id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize database when app starts
init_db()

# ===== CONTACT ROUTES =====

@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    """Get all contacts"""
    conn = get_db_connection()
    contacts = conn.execute('SELECT * FROM contacts ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return jsonify([dict(contact) for contact in contacts])

@app.route('/api/contacts', methods=['POST'])
def create_contact():
    """Create a new contact"""
    data = request.json
    
    # Validate required fields
    if not data.get('name'):
        return jsonify({'error': 'Name is required'}), 400
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO contacts (name, email, phone, company)
        VALUES (?, ?, ?, ?)
    ''', (
        data.get('name'),
        data.get('email'),
        data.get('phone'),
        data.get('company')
    ))
    
    conn.commit()
    new_contact_id = c.lastrowid
    conn.close()
    
    return jsonify({'id': new_contact_id, 'message': 'Contact created'}), 201

@app.route('/api/contacts/<int:contact_id>', methods=['GET'])
def get_contact(contact_id):
    """Get a specific contact"""
    conn = get_db_connection()
    contact = conn.execute('SELECT * FROM contacts WHERE id = ?', (contact_id,)).fetchone()
    conn.close()
    
    if contact is None:
        return jsonify({'error': 'Contact not found'}), 404
    
    return jsonify(dict(contact))

@app.route('/api/contacts/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    """Update a contact"""
    data = request.json
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        UPDATE contacts
        SET name = ?, email = ?, phone = ?, company = ?
        WHERE id = ?
    ''', (
        data.get('name'),
        data.get('email'),
        data.get('phone'),
        data.get('company'),
        contact_id
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Contact updated'})

@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    """Delete a contact"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('DELETE FROM contacts WHERE id = ?', (contact_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Contact deleted'})

# ===== DEAL ROUTES =====

@app.route('/api/deals', methods=['GET'])
def get_deals():
    """Get all deals with contact info"""
    conn = get_db_connection()
    deals = conn.execute('''
        SELECT deals.*, contacts.name as contact_name, contacts.company
        FROM deals
        JOIN contacts ON deals.contact_id = contacts.id
        ORDER BY deals.created_at DESC
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(deal) for deal in deals])

@app.route('/api/deals', methods=['POST'])
def create_deal():
    """Create a new deal"""
    data = request.json
    
    # Validate required fields
    if not data.get('contact_id') or not data.get('deal_name') or not data.get('value'):
        return jsonify({'error': 'contact_id, deal_name, and value are required'}), 400
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO deals (contact_id, deal_name, value, stage, status, probability, lead_source, budget, authority, need, timeline)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('contact_id'),
        data.get('deal_name'),
        data.get('value'),
        data.get('stage', 'qualification'),
        data.get('status', 'open'),
        data.get('probability', 0),
        data.get('lead_source'),
        data.get('budget'),
        data.get('authority'),
        data.get('need'),
        data.get('timeline')
    ))
    
    conn.commit()
    new_deal_id = c.lastrowid
    conn.close()
    
    return jsonify({'id': new_deal_id, 'message': 'Deal created'}), 201

@app.route('/api/deals/<int:deal_id>', methods=['PUT'])
def update_deal(deal_id):
    """Update a deal"""
    data = request.json
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # If status is being set to closed, record the closed_at timestamp
    closed_at = None
    if data.get('status') == 'closed':
        closed_at = datetime.now().isoformat()
    
    c.execute('''
        UPDATE deals
        SET deal_name = ?, value = ?, stage = ?, status = ?, probability = ?, lead_source = ?, budget = ?, authority = ?, need = ?, timeline = ?, closed_at = COALESCE(?, closed_at)
        WHERE id = ?
    ''', (
        data.get('deal_name'),
        data.get('value'),
        data.get('stage'),
        data.get('status'),
        data.get('probability'),
        data.get('lead_source'),
        data.get('budget'),
        data.get('authority'),
        data.get('need'),
        data.get('timeline'),
        closed_at,
        deal_id
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Deal updated'})

@app.route('/api/deals/<int:deal_id>', methods=['DELETE'])
def delete_deal(deal_id):
    """Delete a deal"""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('DELETE FROM deals WHERE id = ?', (deal_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Deal deleted'})

# ===== REVENUE ROUTES =====

@app.route('/api/revenue', methods=['GET'])
def get_revenue():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Realized revenue = closed deals only (all time)
    realized = c.execute('SELECT SUM(value) as total FROM deals WHERE status = ?', ('closed',)).fetchone()
    
    # Pipeline = total value of ALL open deals (not weighted)
    pipeline = c.execute('SELECT SUM(value) as total FROM deals WHERE status = ?', ('open',)).fetchone()
    
    # Forecasted revenue = weighted by probability (open deals only)
    open_deals = c.execute('SELECT value, probability FROM deals WHERE status = ?', ('open',)).fetchall()
    forecasted = sum((deal['value'] * deal['probability'] / 100) for deal in open_deals) if open_deals else 0
    
    conn.close()
    return jsonify({
        'pipeline': pipeline['total'] or 0,
        'forecasted': forecasted,
        'realized': realized['total'] or 0
    })

# ===== ACTIVITIES ROUTES =====

@app.route('/api/activities/<int:deal_id>', methods=['GET'])
def get_activities(deal_id):
    """Get all activities for a deal"""
    conn = get_db_connection()
    activities = conn.execute(
        'SELECT * FROM activities WHERE deal_id = ? ORDER BY created_at DESC',
        (deal_id,)
    ).fetchall()
    conn.close()
    
    return jsonify([dict(activity) for activity in activities])

@app.route('/api/activities', methods=['POST'])
def create_activity():
    """Create a new activity"""
    data = request.json
    
    if not data.get('deal_id') or not data.get('activity_type'):
        return jsonify({'error': 'deal_id and activity_type are required'}), 400
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO activities (deal_id, activity_type, description)
        VALUES (?, ?, ?)
    ''', (
        data.get('deal_id'),
        data.get('activity_type'),
        data.get('description')
    ))
    
    conn.commit()
    new_activity_id = c.lastrowid
    conn.close()
    
    return jsonify({'id': new_activity_id, 'message': 'Activity created'}), 201

# ===== HEALTH CHECK =====

@app.route('/api/health', methods=['GET'])
def health():
    """Simple health check to verify the app is running"""
    return jsonify({'status': 'CRM Backend is running!'}), 200
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('.', path)
@app.route('/')
def serve_html():
    with open('index.html', 'r') as f:
        return f.read()

if __name__ == '__main__':
    app.run(debug=True, port=5000)