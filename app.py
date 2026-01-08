from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

DATABASE = 'crm.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Contacts table with new fields
    c.execute('''CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        company TEXT,
        title TEXT,
        website TEXT,
        additional_info TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # SKU table
    c.execute('''CREATE TABLE IF NOT EXISTS skus (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        subcategory TEXT NOT NULL,
        UNIQUE(name, category, subcategory)
    )''')
    
    # Opportunities table - added expected_close_date
    c.execute('''CREATE TABLE IF NOT EXISTS deals (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        contact_id INTEGER,
        value REAL,
        probability INTEGER,
        stage TEXT,
        status TEXT,
        lead_source TEXT,
        budget TEXT,
        authority TEXT,
        need TEXT,
        timeline TEXT,
        expected_close_date TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(contact_id) REFERENCES contacts(id)
    )''')
    
    # Opportunity-SKU junction table (many-to-many)
    c.execute('''CREATE TABLE IF NOT EXISTS deal_skus (
        id INTEGER PRIMARY KEY,
        deal_id INTEGER NOT NULL,
        sku_id INTEGER NOT NULL,
        FOREIGN KEY(deal_id) REFERENCES deals(id) ON DELETE CASCADE,
        FOREIGN KEY(sku_id) REFERENCES skus(id) ON DELETE CASCADE,
        UNIQUE(deal_id, sku_id)
    )''')
    
    # Activities table - added next_steps
    c.execute('''CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY,
        deal_id INTEGER,
        contact_id INTEGER,
        type TEXT,
        description TEXT,
        next_steps TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(deal_id) REFERENCES deals(id),
        FOREIGN KEY(contact_id) REFERENCES contacts(id)
    )''')
    
    conn.commit()
    conn.close()

def migrate_db():
    """Add new columns if they don't exist"""
    conn = get_db()
    c = conn.cursor()
    
    # Check and add expected_close_date to deals
    try:
        c.execute("ALTER TABLE deals ADD COLUMN expected_close_date TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Check and add next_steps to activities
    try:
        c.execute("ALTER TABLE activities ADD COLUMN next_steps TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.close()

def populate_skus():
    """Populate SKU table with predefined values"""
    conn = get_db()
    c = conn.cursor()
    
    skus = [
        # Raw Materials - Fiber
        ('Premium Clean Long Fiber', 'Raw Materials', 'Fiber'),
        ('Non-woven Grade, Clean Fiber', 'Raw Materials', 'Fiber'),
        ('Short Fiber/Hurd Mix', 'Raw Materials', 'Fiber'),
        # Raw Materials - Hurd
        ('H1 Hurd - 3/4"', 'Raw Materials', 'Hurd'),
        ('H2 Hurd - 1/2"', 'Raw Materials', 'Hurd'),
        ('H3 Hurd - 1/16"', 'Raw Materials', 'Hurd'),
        # Products - Insulation
        ('2"x24"x48"', 'Products', 'Insulation'),
        ('3.5"x24"x48"', 'Products', 'Insulation'),
        ('5.5"x24"x48"', 'Products', 'Insulation'),
        ('7.5"x24"x48"', 'Products', 'Insulation'),
        # Products - Acoustic Panels
        ('1"x24"x48"', 'Products', 'Acoustic Panels'),
        ('2"x24"x48"', 'Products', 'Acoustic Panels'),
        ('4"x24"x48"', 'Products', 'Acoustic Panels'),
    ]
    
    for sku_name, category, subcategory in skus:
        try:
            c.execute('INSERT INTO skus (name, category, subcategory) VALUES (?, ?, ?)',
                     (sku_name, category, subcategory))
        except sqlite3.IntegrityError:
            pass  # SKU already exists
    
    conn.commit()
    conn.close()

init_db()
migrate_db()
populate_skus()

# ==================== CONTACTS ENDPOINTS ====================

@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM contacts ORDER BY name')
    contacts = c.fetchall()
    conn.close()
    return jsonify([dict(contact) for contact in contacts])

@app.route('/api/contacts', methods=['POST'])
def add_contact():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO contacts (name, email, phone, company, title, website, additional_info)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
             (data.get('name'), data.get('email'), data.get('phone'), 
              data.get('company'), data.get('title'), data.get('website'),
              data.get('additional_info')))
    conn.commit()
    contact_id = c.lastrowid
    conn.close()
    return jsonify({'id': contact_id}), 201

@app.route('/api/contacts/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute('''UPDATE contacts 
                 SET name=?, email=?, phone=?, company=?, title=?, website=?, additional_info=?
                 WHERE id=?''',
             (data.get('name'), data.get('email'), data.get('phone'),
              data.get('company'), data.get('title'), data.get('website'),
              data.get('additional_info'), contact_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM contacts WHERE id=?', (contact_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ==================== SKU ENDPOINTS ====================

@app.route('/api/skus', methods=['GET'])
def get_skus():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM skus ORDER BY category, subcategory, name')
    skus = c.fetchall()
    conn.close()
    
    # Organize SKUs by category and subcategory
    organized = {}
    for sku in skus:
        cat = sku['category']
        subcat = sku['subcategory']
        if cat not in organized:
            organized[cat] = {}
        if subcat not in organized[cat]:
            organized[cat][subcat] = []
        organized[cat][subcat].append(dict(sku))
    
    return jsonify(organized)

# ==================== DEALS/OPPORTUNITIES ENDPOINTS ====================

@app.route('/api/deals', methods=['GET'])
def get_deals():
    conn = get_db()
    c = conn.cursor()
    c.execute('''SELECT d.*, c.name as contact_name FROM deals d
                 LEFT JOIN contacts c ON d.contact_id = c.id
                 ORDER BY d.created_at DESC''')
    deals = c.fetchall()
    
    deals_list = []
    for deal in deals:
        deal_dict = dict(deal)
        # Get SKUs for this deal
        c.execute('''SELECT s.* FROM skus s
                     INNER JOIN deal_skus ds ON s.id = ds.sku_id
                     WHERE ds.deal_id = ?''', (deal['id'],))
        skus = c.fetchall()
        deal_dict['skus'] = [dict(sku) for sku in skus]
        deals_list.append(deal_dict)
    
    conn.close()
    return jsonify(deals_list)

@app.route('/api/deals', methods=['POST'])
def add_deal():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''INSERT INTO deals (name, contact_id, value, probability, stage, status, 
                                    lead_source, budget, authority, need, timeline, expected_close_date)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
             (data.get('name'), data.get('contact_id'), data.get('value'),
              data.get('probability'), data.get('stage'), data.get('status'),
              data.get('lead_source'), data.get('budget'), data.get('authority'),
              data.get('need'), data.get('timeline'), data.get('expected_close_date')))
    
    deal_id = c.lastrowid
    
    # Add SKUs to the deal
    sku_ids = data.get('sku_ids', [])
    for sku_id in sku_ids:
        c.execute('INSERT INTO deal_skus (deal_id, sku_id) VALUES (?, ?)', 
                 (deal_id, sku_id))
    
    conn.commit()
    conn.close()
    return jsonify({'id': deal_id}), 201

@app.route('/api/deals/<int:deal_id>', methods=['PUT'])
def update_deal(deal_id):
    data = request.json
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''UPDATE deals 
                 SET name=?, contact_id=?, value=?, probability=?, stage=?, status=?,
                     lead_source=?, budget=?, authority=?, need=?, timeline=?, expected_close_date=?
                 WHERE id=?''',
             (data.get('name'), data.get('contact_id'), data.get('value'),
              data.get('probability'), data.get('stage'), data.get('status'),
              data.get('lead_source'), data.get('budget'), data.get('authority'),
              data.get('need'), data.get('timeline'), data.get('expected_close_date'), deal_id))
    
    # Update SKUs - delete old ones and add new ones
    c.execute('DELETE FROM deal_skus WHERE deal_id=?', (deal_id,))
    sku_ids = data.get('sku_ids', [])
    for sku_id in sku_ids:
        c.execute('INSERT INTO deal_skus (deal_id, sku_id) VALUES (?, ?)', 
                 (deal_id, sku_id))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/deals/<int:deal_id>', methods=['DELETE'])
def delete_deal(deal_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM deals WHERE id=?', (deal_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ==================== ACTIVITIES ENDPOINTS ====================

@app.route('/api/activities', methods=['GET'])
def get_activities():
    deal_id = request.args.get('deal_id')
    conn = get_db()
    c = conn.cursor()
    
    if deal_id:
        c.execute('SELECT * FROM activities WHERE deal_id=? ORDER BY created_at DESC', (deal_id,))
    else:
        c.execute('SELECT * FROM activities ORDER BY created_at DESC')
    
    activities = c.fetchall()
    conn.close()
    return jsonify([dict(activity) for activity in activities])

@app.route('/api/activities', methods=['POST'])
def add_activity():
    data = request.json
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO activities (deal_id, contact_id, type, description, next_steps)
                 VALUES (?, ?, ?, ?, ?)''',
             (data.get('deal_id'), data.get('contact_id'), data.get('type'), 
              data.get('description'), data.get('next_steps')))
    conn.commit()
    conn.close()
    return jsonify({'success': True}), 201

# ==================== REVENUE/METRICS ENDPOINTS ====================

@app.route('/api/revenue', methods=['GET'])
def get_revenue():
    conn = get_db()
    c = conn.cursor()
    
    realized = c.execute('SELECT SUM(value) as total FROM deals WHERE status = ?', ('closed',)).fetchone()
    pipeline = c.execute('SELECT SUM(value) as total FROM deals WHERE status = ?', ('open',)).fetchone()
    open_deals = c.execute('SELECT value, probability FROM deals WHERE status = ?', ('open',)).fetchall()
    
    forecasted = sum((deal['value'] * deal['probability'] / 100) for deal in open_deals if deal['value'] and deal['probability'])
    
    conn.close()
    return jsonify({
        'pipeline': pipeline['total'] or 0,
        'forecasted': forecasted,
        'realized': realized['total'] or 0
    })

# ==================== PIPELINE ANALYTICS ENDPOINT ====================

@app.route('/api/pipeline/analytics', methods=['GET'])
def get_pipeline_analytics():
    conn = get_db()
    c = conn.cursor()
    
    # Get all open deals with details
    c.execute('''SELECT d.*, c.name as contact_name FROM deals d
                 LEFT JOIN contacts c ON d.contact_id = c.id
                 WHERE d.status = 'open'
                 ORDER BY d.expected_close_date ASC, d.value DESC''')
    deals = c.fetchall()
    
    # Organize by stage
    stages = {}
    stage_order = ['qualification', 'needs_analysis', 'proposal', 'negotiation']
    
    for stage in stage_order:
        stages[stage] = {
            'deals': [],
            'total_value': 0,
            'weighted_value': 0,
            'count': 0
        }
    
    for deal in deals:
        deal_dict = dict(deal)
        stage = deal['stage']
        if stage in stages:
            # Get SKUs for this deal
            c.execute('''SELECT s.* FROM skus s
                         INNER JOIN deal_skus ds ON s.id = ds.sku_id
                         WHERE ds.deal_id = ?''', (deal['id'],))
            skus = c.fetchall()
            deal_dict['skus'] = [dict(sku) for sku in skus]
            
            stages[stage]['deals'].append(deal_dict)
            stages[stage]['total_value'] += deal['value'] or 0
            stages[stage]['weighted_value'] += (deal['value'] or 0) * (deal['probability'] or 0) / 100
            stages[stage]['count'] += 1
    
    # Calculate totals
    total_pipeline = sum(s['total_value'] for s in stages.values())
    total_weighted = sum(s['weighted_value'] for s in stages.values())
    total_deals = sum(s['count'] for s in stages.values())
    
    # Group by expected close date (monthly)
    monthly_forecast = {}
    for deal in deals:
        close_date = deal['expected_close_date']
        if close_date:
            month_key = close_date[:7]  # YYYY-MM
        else:
            month_key = 'No Date Set'
        
        if month_key not in monthly_forecast:
            monthly_forecast[month_key] = {'total': 0, 'weighted': 0, 'count': 0}
        
        monthly_forecast[month_key]['total'] += deal['value'] or 0
        monthly_forecast[month_key]['weighted'] += (deal['value'] or 0) * (deal['probability'] or 0) / 100
        monthly_forecast[month_key]['count'] += 1
    
    conn.close()
    
    return jsonify({
        'stages': stages,
        'monthly_forecast': monthly_forecast,
        'totals': {
            'pipeline': total_pipeline,
            'weighted': total_weighted,
            'deal_count': total_deals
        }
    })

# ==================== SERVE HTML ====================

@app.route('/')
def serve_index():
    try:
        with open('index.html', 'r') as f:
            return f.read(), 200, {'Content-Type': 'text/html'}
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    try:
        with open(f'assets/{filename}', 'rb') as f:
            if filename.endswith('.png'):
                return f.read(), 200, {'Content-Type': 'image/png'}
            elif filename.endswith('.jpg'):
                return f.read(), 200, {'Content-Type': 'image/jpeg'}
            else:
                return f.read(), 200, {'Content-Type': 'application/octet-stream'}
    except Exception as e:
        return f"Asset not found: {str(e)}", 404

if __name__ == '__main__':
    app.run(debug=False, port=3000, host='0.0.0.0')