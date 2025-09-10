from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash, g
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename
import uuid
import sqlite3
import logging
from functools import wraps
import hashlib
import secrets

# Import our custom classes
from eu_regulatory_scraper import EURegulatoryScraper
from ai_compliance_analyzer import AIComplianceAnalyzer
from report_generator import ComplianceReportGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('web_app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')  # Use environment variable in production

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database configuration
DATABASE = 'compliance.db'

# Initialize our components
scraper = EURegulatoryScraper()
analyzer = AIComplianceAnalyzer(api_key=os.environ.get('DEEPSEEK_API_KEY', 'your-deepseek-api-key'))
report_generator = ComplianceReportGenerator()

def get_db():
    """
    Get database connection
    """
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """
    Close database connection
    """
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """
    Initialize database with required tables
    """
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # Create clients table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            business_info TEXT,
            created_at TEXT NOT NULL,
            last_login TEXT
        )
        ''')
        
        # Create reports table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            business_info TEXT NOT NULL,
            analysis_result TEXT NOT NULL,
            roadmap TEXT NOT NULL,
            cost_estimate TEXT NOT NULL,
            compliance_report_path TEXT NOT NULL,
            roadmap_report_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
        ''')
        
        # Create regulatory_updates table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS regulatory_updates (
            id TEXT PRIMARY KEY,
            regulation_type TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            url TEXT NOT NULL,
            date TEXT NOT NULL,
            discovered_date TEXT NOT NULL
        )
        ''')
        
        db.commit()

def login_required(f):
    """
    Decorator to require login
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'client_id' not in session:
            flash('You must be logged in to access this page', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def hash_password(password):
    """
    Hash password using SHA-256
    """
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Client dashboard"""
    client_id = session['client_id']
    
    # Get client information
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
    client = cursor.fetchone()
    
    if not client:
        flash('Client not found', 'danger')
        return redirect(url_for('logout'))
    
    # Get client reports
    cursor.execute('SELECT * FROM reports WHERE client_id = ? ORDER BY created_at DESC', (client_id,))
    reports = cursor.fetchall()
    
    # Convert to dict for easier handling in templates
    client_dict = dict(client)
    reports_list = [dict(report) for report in reports]
    
    # Parse business_info if it exists
    if client_dict['business_info']:
        try:
            client_dict['business_info'] = json.loads(client_dict['business_info'])
        except:
            client_dict['business_info'] = {}
    else:
        client_dict['business_info'] = {}
    
    # Parse analysis results for reports
    for report in reports_list:
        try:
            report['analysis_result'] = json.loads(report['analysis_result'])
        except:
            report['analysis_result'] = {}
    
    return render_template('dashboard.html', client=client_dict, reports=reports_list)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Client registration"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate input
        if not email or not password:
            flash('Email and password are required', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        # Check if email already exists
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id FROM clients WHERE email = ?', (email,))
        existing_client = cursor.fetchone()
        
        if existing_client:
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        # Create new client
        client_id = f"client_{uuid.uuid4().hex[:8]}"
        password_hash = hash_password(password)
        created_at = datetime.now().isoformat()
        
        try:
            cursor.execute(
                'INSERT INTO clients (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)',
                (client_id, email, password_hash, created_at)
            )
            db.commit()
            
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            logger.error(f"Error creating client: {str(e)}")
            flash('Registration failed. Please try again.', 'danger')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Client login"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Validate input
        if not email or not password:
            flash('Email and password are required', 'danger')
            return render_template('login.html')
        
        # Check client credentials
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM clients WHERE email = ?', (email,))
        client = cursor.fetchone()
        
        if not client or client['password_hash'] != hash_password(password):
            flash('Invalid email or password', 'danger')
            return render_template('login.html')
        
        # Update last login
        cursor.execute(
            'UPDATE clients SET last_login = ? WHERE id = ?',
            (datetime.now().isoformat(), client['id'])
        )
        db.commit()
        
        # Set session
        session['client_id'] = client['id']
        
        flash('Login successful', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Client logout"""
    session.pop('client_id', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/business-info', methods=['GET', 'POST'])
@login_required
def business_info():
    """Collect business information"""
    client_id = session['client_id']
    
    # Get client information
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
    client = cursor.fetchone()
    
    if not client:
        flash('Client not found', 'danger')
        return redirect(url_for('logout'))
    
    # Get existing business info
    business_info = {}
    if client['business_info']:
        try:
            business_info = json.loads(client['business_info'])
        except:
            business_info = {}
    
    if request.method == 'POST':
        # Collect business information
        business_info = {
            'business_name': request.form.get('business_name'),
            'industry': request.form.get('industry'),
            'business_activities': request.form.get('business_activities'),
            'target_markets': request.form.get('target_markets'),
            'data_processing': request.form.get('data_processing'),
            'ai_systems': request.form.get('ai_systems'),
            'online_services': request.form.get('online_services'),
            'current_compliance': request.form.get('current_compliance')
        }
        
        # Save to client record
        try:
            cursor.execute(
                'UPDATE clients SET business_info = ? WHERE id = ?',
                (json.dumps(business_info), client_id)
            )
            db.commit()
            
            flash('Business information saved successfully', 'success')
            return redirect(url_for('compliance_analysis'))
            
        except Exception as e:
            logger.error(f"Error saving business info: {str(e)}")
            flash('Failed to save business information', 'danger')
    
    return render_template('business_info.html', business_info=business_info)

@app.route('/compliance-analysis', methods=['GET', 'POST'])
@login_required
def compliance_analysis():
    """Perform compliance analysis"""
    client_id = session['client_id']
    
    # Get client information
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
    client = cursor.fetchone()
    
    if not client:
        flash('Client not found', 'danger')
        return redirect(url_for('logout'))
    
    # Get business info
    business_info = {}
    if client['business_info']:
        try:
            business_info = json.loads(client['business_info'])
        except:
            business_info = {}
    
    if not business_info:
        flash('Please provide business information first', 'warning')
        return redirect(url_for('business_info'))
    
    if request.method == 'POST':
        try:
            # Perform compliance analysis
            analysis_result = analyzer.analyze_compliance(business_info)
            
            # Generate roadmap
            roadmap = analyzer.generate_compliance_roadmap(analysis_result)
            
            # Estimate costs
            cost_estimate = analyzer.estimate_compliance_costs(analysis_result)
            
            # Save analysis result
            report_id = f"report_{uuid.uuid4().hex[:8]}"
            created_at = datetime.now().isoformat()
            
            # Generate PDF reports
            compliance_report_path = report_generator.generate_compliance_report(analysis_result, business_info)
            roadmap_report_path = report_generator.generate_roadmap_report(roadmap, business_info)
            
            # Save to database
            cursor.execute('''
            INSERT INTO reports (
                id, client_id, business_info, analysis_result, roadmap, cost_estimate,
                compliance_report_path, roadmap_report_path, created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                report_id, client_id, json.dumps(business_info), json.dumps(analysis_result),
                json.dumps(roadmap), json.dumps(cost_estimate), compliance_report_path,
                roadmap_report_path, created_at, 'completed'
            ))
            db.commit()
            
            flash('Compliance analysis completed successfully', 'success')
            return redirect(url_for('view_report', report_id=report_id))
            
        except Exception as e:
            logger.error(f"Error performing compliance analysis: {str(e)}")
            flash('Failed to perform compliance analysis', 'danger')
    
    return render_template('compliance_analysis.html', business_info=business_info)

@app.route('/report/<report_id>')
@login_required
def view_report(report_id):
    """View compliance report"""
    client_id = session['client_id']
    
    # Get report from database
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM reports WHERE id = ? AND client_id = ?', (report_id, client_id))
    report = cursor.fetchone()
    
    if not report:
        flash('Report not found', 'danger')
        return redirect(url_for('dashboard'))
    
    # Convert to dict and parse JSON fields
    report_dict = dict(report)
    try:
        report_dict['analysis_result'] = json.loads(report_dict['analysis_result'])
        report_dict['roadmap'] = json.loads(report_dict['roadmap'])
        report_dict['cost_estimate'] = json.loads(report_dict['cost_estimate'])
        report_dict['business_info'] = json.loads(report_dict['business_info'])
    except Exception as e:
        logger.error(f"Error parsing report data: {str(e)}")
        flash('Error loading report data', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('view_report.html', report=report_dict)

@app.route('/download/<report_id>/<report_type>')
@login_required
def download_report(report_id, report_type):
    """Download compliance report"""
    client_id = session['client_id']
    
    # Get report from database
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM reports WHERE id = ? AND client_id = ?', (report_id, client_id))
    report = cursor.fetchone()
    
    if not report:
        flash('Report not found', 'danger')
        return redirect(url_for('dashboard'))
    
    if report_type == 'compliance':
        file_path = report['compliance_report_path']
        filename = f"Compliance_Report_{report_id}.pdf"
    elif report_type == 'roadmap':
        file_path = report['roadmap_report_path']
        filename = f"Compliance_Roadmap_{report_id}.pdf"
    else:
        flash('Invalid report type', 'danger')
        return redirect(url_for('view_report', report_id=report_id))
    
    if not file_path or not os.path.exists(file_path):
        flash('Report file not found', 'danger')
        return redirect(url_for('view_report', report_id=report_id))
    
    return send_file(file_path, as_attachment=True, download_name=filename)

@app.route('/api/regulatory-updates')
def api_regulatory_updates():
    """API endpoint for regulatory updates"""
    regulation_type = request.args.get('type', 'all')
    
    try:
        if regulation_type == 'all':
            updates = scraper.check_for_updates()
        else:
            updates = {regulation_type: scraper.scrape_regulation_updates(regulation_type)}
        
        return jsonify(updates)
    except Exception as e:
        logger.error(f"Error getting regulatory updates: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-compliance', methods=['POST'])
def api_analyze_compliance():
    """API endpoint for compliance analysis"""
    data = request.get_json()
    business_info = data.get('business_info', {})
    
    if not business_info:
        return jsonify({'error': 'Business information required'}), 400
    
    try:
        # Perform compliance analysis
        analysis_result = analyzer.analyze_compliance(business_info)
        
        return jsonify(analysis_result)
    except Exception as e:
        logger.error(f"Error in compliance analysis API: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Initialize database
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)