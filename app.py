from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import time
from datetime import datetime
import traceback
import os

app = Flask(__name__)
CORS(app)

# Database configuration - use PostgreSQL if DATABASE_URL exists, otherwise SQLite
DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    # Fix for Render's postgres:// URL (should be postgresql://)
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    print(f"Using PostgreSQL database")
else:
    import sqlite3
    DATABASE = 'crm.db'
    print(f"Using SQLite database: {DATABASE}")

def get_db():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(DATABASE, timeout=60)
        conn.row_factory = sqlite3.Row
        return conn

def convert_query(query):
    """Convert SQLite ? placeholders to PostgreSQL %s if needed"""
    if USE_POSTGRES:
        return query.replace('?', '%s')
    return query

def execute_with_retry(func, max_retries=5):
    """Execute a database function with retry logic for locked database"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            # Handle both SQLite and PostgreSQL errors
            error_str = str(e).lower()
            is_retryable = "locked" in error_str or "deadlock" in error_str

            if is_retryable and attempt < max_retries - 1:
                print(f"Database locked/busy, retrying in {attempt + 1} seconds...")
                time.sleep(attempt + 1)  # Exponential backoff
            else:
                raise

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Database-specific setup
    if not USE_POSTGRES:
        # Enable WAL mode for SQLite better concurrency
        c.execute('PRAGMA journal_mode=WAL')
        print("WAL mode enabled")

    # Define data types based on database
    if USE_POSTGRES:
        pk_type = "SERIAL PRIMARY KEY"
        timestamp_default = "DEFAULT NOW()"
    else:
        pk_type = "INTEGER PRIMARY KEY"
        timestamp_default = "DEFAULT CURRENT_TIMESTAMP"

    # Contacts table with new fields
    c.execute(f'''CREATE TABLE IF NOT EXISTS contacts (
        id {pk_type},
        name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        company TEXT,
        title TEXT,
        website TEXT,
        additional_info TEXT,
        created_at TIMESTAMP {timestamp_default}
    )''')

    # SKU table
    c.execute(f'''CREATE TABLE IF NOT EXISTS skus (
        id {pk_type},
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        subcategory TEXT NOT NULL,
        UNIQUE(name, category, subcategory)
    )''')

    # Opportunities table - added expected_close_date
    c.execute(f'''CREATE TABLE IF NOT EXISTS deals (
        id {pk_type},
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
        created_at TIMESTAMP {timestamp_default},
        FOREIGN KEY(contact_id) REFERENCES contacts(id)
    )''')

    # Opportunity-SKU junction table (many-to-many)
    c.execute(f'''CREATE TABLE IF NOT EXISTS deal_skus (
        id {pk_type},
        deal_id INTEGER NOT NULL,
        sku_id INTEGER NOT NULL,
        FOREIGN KEY(deal_id) REFERENCES deals(id) ON DELETE CASCADE,
        FOREIGN KEY(sku_id) REFERENCES skus(id) ON DELETE CASCADE,
        UNIQUE(deal_id, sku_id)
    )''')

    # Activities table - added next_steps
    c.execute(f'''CREATE TABLE IF NOT EXISTS activities (
        id {pk_type},
        deal_id INTEGER,
        contact_id INTEGER,
        type TEXT,
        description TEXT,
        next_steps TEXT,
        created_at TIMESTAMP {timestamp_default},
        FOREIGN KEY(deal_id) REFERENCES deals(id),
        FOREIGN KEY(contact_id) REFERENCES contacts(id)
    )''')

    conn.commit()
    conn.close()
    print("Database initialized successfully")

def migrate_db():
    """Add new columns if they don't exist - comprehensive migration"""
    conn = get_db()
    c = conn.cursor()

    # Get existing columns in contacts table
    if USE_POSTGRES:
        c.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'contacts'
        """)
        contacts_columns = [row['column_name'] for row in c.fetchall()]
    else:
        c.execute("PRAGMA table_info(contacts)")
        contacts_columns = [row[1] for row in c.fetchall()]

    print(f"Existing contacts columns: {contacts_columns}")
    
    # Add missing columns to contacts
    contacts_migrations = [
        ("title", "TEXT"),
        ("website", "TEXT"),
        ("additional_info", "TEXT"),
    ]
    
    for col_name, col_type in contacts_migrations:
        if col_name not in contacts_columns:
            try:
                c.execute(f"ALTER TABLE contacts ADD COLUMN {col_name} {col_type}")
                print(f"Added column {col_name} to contacts")
            except Exception as e:
                print(f"Error adding {col_name} to contacts: {e}")
    
    # Get existing columns in deals table
    if USE_POSTGRES:
        c.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'deals'
        """)
        deals_columns = [row['column_name'] for row in c.fetchall()]
    else:
        c.execute("PRAGMA table_info(deals)")
        deals_columns = [row[1] for row in c.fetchall()]

    print(f"Existing deals columns: {deals_columns}")
    
    # Add missing columns to deals
    deals_migrations = [
        ("name", "TEXT"),
        ("contact_id", "INTEGER"),
        ("value", "REAL"),
        ("probability", "INTEGER"),
        ("stage", "TEXT"),
        ("status", "TEXT"),
        ("lead_source", "TEXT"),
        ("budget", "TEXT"),
        ("authority", "TEXT"),
        ("need", "TEXT"),
        ("timeline", "TEXT"),
        ("expected_close_date", "TEXT"),
    ]
    
    for col_name, col_type in deals_migrations:
        if col_name not in deals_columns:
            try:
                c.execute(f"ALTER TABLE deals ADD COLUMN {col_name} {col_type}")
                print(f"Added column {col_name} to deals")
            except Exception as e:
                print(f"Error adding {col_name} to deals: {e}")
    
    # Get existing columns in activities table
    if USE_POSTGRES:
        c.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'activities'
        """)
        activities_columns = [row['column_name'] for row in c.fetchall()]
    else:
        c.execute("PRAGMA table_info(activities)")
        activities_columns = [row[1] for row in c.fetchall()]

    print(f"Existing activities columns: {activities_columns}")
    
    # Add missing columns to activities
    activities_migrations = [
        ("next_steps", "TEXT"),
    ]
    
    for col_name, col_type in activities_migrations:
        if col_name not in activities_columns:
            try:
                c.execute(f"ALTER TABLE activities ADD COLUMN {col_name} {col_type}")
                print(f"Added column {col_name} to activities")
            except Exception as e:
                print(f"Error adding {col_name} to activities: {e}")
    
    conn.commit()
    conn.close()
    print("Migration complete!")

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
            if USE_POSTGRES:
                c.execute('INSERT INTO skus (name, category, subcategory) VALUES (%s, %s, %s)',
                         (sku_name, category, subcategory))
            else:
                c.execute('INSERT INTO skus (name, category, subcategory) VALUES (?, ?, ?)',
                         (sku_name, category, subcategory))
        except Exception:
            pass  # SKU already exists (IntegrityError for both SQLite and PostgreSQL)
    
    conn.commit()
    conn.close()
    print("SKUs populated successfully")

print("Starting database initialization...")
init_db()
migrate_db()
populate_skus()
print("Database setup complete!")

# ==================== CONTACTS ENDPOINTS ====================

@app.route('/api/contacts', methods=['GET'])
def get_contacts():
    def do_get():
        conn = get_db()
        try:
            c = conn.cursor()
            c.execute('SELECT * FROM contacts ORDER BY name')
            contacts = c.fetchall()
            return [dict(contact) for contact in contacts]
        finally:
            conn.close()

    try:
        contacts = execute_with_retry(do_get)
        return jsonify(contacts)
    except Exception as e:
        print(f"Error in get_contacts: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contacts', methods=['POST'])
def add_contact():
    def do_add():
        data = request.json
        conn = get_db()
        try:
            c = conn.cursor()
            c.execute('''INSERT INTO contacts (name, email, phone, company, title, website, additional_info)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (data.get('name'), data.get('email'), data.get('phone'),
                      data.get('company'), data.get('title'), data.get('website'),
                      data.get('additional_info')))
            conn.commit()
            return c.lastrowid
        finally:
            conn.close()

    try:
        contact_id = execute_with_retry(do_add)
        return jsonify({'id': contact_id}), 201
    except Exception as e:
        print(f"Error in add_contact: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contacts/<int:contact_id>', methods=['PUT'])
def update_contact(contact_id):
    def do_update():
        data = request.json
        conn = get_db()
        try:
            c = conn.cursor()
            c.execute('''UPDATE contacts
                         SET name=?, email=?, phone=?, company=?, title=?, website=?, additional_info=?
                         WHERE id=?''',
                     (data.get('name'), data.get('email'), data.get('phone'),
                      data.get('company'), data.get('title'), data.get('website'),
                      data.get('additional_info'), contact_id))
            conn.commit()
            return True
        finally:
            conn.close()

    try:
        execute_with_retry(do_update)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in update_contact: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
def delete_contact(contact_id):
    def do_delete():
        conn = get_db()
        try:
            c = conn.cursor()
            c.execute('DELETE FROM contacts WHERE id=?', (contact_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    try:
        execute_with_retry(do_delete)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in delete_contact: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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
    def do_get():
        conn = get_db()
        try:
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

            return deals_list
        finally:
            conn.close()

    try:
        deals_list = execute_with_retry(do_get)
        return jsonify(deals_list)
    except Exception as e:
        print(f"Error in get_deals: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/deals', methods=['POST'])
def add_deal():
    def do_add():
        conn = get_db()
        try:
            data = request.json
            print(f"Adding deal with data: {data}")
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
            print(f"Deal created successfully with id: {deal_id}")
            return deal_id
        finally:
            conn.close()
    
    try:
        deal_id = execute_with_retry(do_add)
        return jsonify({'id': deal_id}), 201
    except Exception as e:
        print(f"Error in add_deal: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/deals/<int:deal_id>', methods=['PUT'])
def update_deal(deal_id):
    def do_update():
        data = request.json
        print(f"Updating deal {deal_id} with data: {data}")
        conn = get_db()
        try:
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
            print(f"Deal {deal_id} updated successfully")
            return True
        finally:
            conn.close()
    
    try:
        execute_with_retry(do_update)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in update_deal: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/deals/<int:deal_id>', methods=['DELETE'])
def delete_deal(deal_id):
    def do_delete():
        conn = get_db()
        try:
            c = conn.cursor()
            c.execute('DELETE FROM deals WHERE id=?', (deal_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    try:
        execute_with_retry(do_delete)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error in delete_deal: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ==================== ACTIVITIES ENDPOINTS ====================

@app.route('/api/activities', methods=['GET'])
def get_activities():
    def do_get():
        deal_id = request.args.get('deal_id')
        conn = get_db()
        try:
            c = conn.cursor()

            if deal_id:
                c.execute('SELECT * FROM activities WHERE deal_id=? ORDER BY created_at DESC', (deal_id,))
            else:
                c.execute('SELECT * FROM activities ORDER BY created_at DESC')

            activities = c.fetchall()
            return [dict(activity) for activity in activities]
        finally:
            conn.close()

    try:
        activities = execute_with_retry(do_get)
        return jsonify(activities)
    except Exception as e:
        print(f"Error in get_activities: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/activities', methods=['POST'])
def add_activity():
    def do_add():
        data = request.json
        conn = get_db()
        try:
            c = conn.cursor()
            c.execute('''INSERT INTO activities (deal_id, contact_id, type, description, next_steps)
                         VALUES (?, ?, ?, ?, ?)''',
                     (data.get('deal_id'), data.get('contact_id'), data.get('type'),
                      data.get('description'), data.get('next_steps')))
            conn.commit()
            return True
        finally:
            conn.close()

    try:
        execute_with_retry(do_add)
        return jsonify({'success': True}), 201
    except Exception as e:
        print(f"Error in add_activity: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ==================== REVENUE/METRICS ENDPOINTS ====================

@app.route('/api/revenue', methods=['GET'])
def get_revenue():
    def do_get():
        conn = get_db()
        try:
            c = conn.cursor()

            realized = c.execute('SELECT SUM(value) as total FROM deals WHERE status = ?', ('closed',)).fetchone()
            pipeline = c.execute('SELECT SUM(value) as total FROM deals WHERE status = ?', ('open',)).fetchone()
            open_deals = c.execute('SELECT value, probability FROM deals WHERE status = ?', ('open',)).fetchall()

            forecasted = sum((deal['value'] * deal['probability'] / 100) for deal in open_deals if deal['value'] and deal['probability'])

            return {
                'pipeline': pipeline['total'] or 0,
                'forecasted': forecasted,
                'realized': realized['total'] or 0
            }
        finally:
            conn.close()

    try:
        revenue = execute_with_retry(do_get)
        return jsonify(revenue)
    except Exception as e:
        print(f"Error in get_revenue: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# ==================== PIPELINE ANALYTICS ENDPOINT ====================

@app.route('/api/pipeline/analytics', methods=['GET'])
def get_pipeline_analytics():
    def do_get():
        conn = get_db()
        try:
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
                close_date = deal['expected_close_date'] if 'expected_close_date' in deal.keys() else None
                if close_date:
                    month_key = close_date[:7]  # YYYY-MM
                else:
                    month_key = 'No Date Set'

                if month_key not in monthly_forecast:
                    monthly_forecast[month_key] = {'total': 0, 'weighted': 0, 'count': 0}

                monthly_forecast[month_key]['total'] += deal['value'] or 0
                monthly_forecast[month_key]['weighted'] += (deal['value'] or 0) * (deal['probability'] or 0) / 100
                monthly_forecast[month_key]['count'] += 1

            return {
                'stages': stages,
                'monthly_forecast': monthly_forecast,
                'totals': {
                    'pipeline': total_pipeline,
                    'weighted': total_weighted,
                    'deal_count': total_deals
                }
            }
        finally:
            conn.close()

    try:
        analytics = execute_with_retry(do_get)
        return jsonify(analytics)
    except Exception as e:
        print(f"Error in get_pipeline_analytics: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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