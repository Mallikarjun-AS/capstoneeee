from flask import Flask, render_template, redirect, url_for, request, session, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from flask_cors import CORS
from flask_mail import Mail, Message
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import razorpay
import os
from datetime import datetime
import sqlite3
import requests
import time
import hashlib
from threading import Lock
import json
from functools import lru_cache
from io import BytesIO
import base64

app = Flask(__name__)
app.secret_key = 'museumhub-secret-key-2024'

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:3110@localhost/museum_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Razorpay Keys
app.config['RAZORPAY_KEY_ID'] = "rzp_test_asfsdiohnJBNrv"
app.config['RAZORPAY_KEY_SECRET'] = "87JHBb79KADBbwrasda"

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = "yourmail@gmail.com"
app.config['MAIL_PASSWORD'] = "asdethxbguxfbgjef"
app.config['MAIL_DEFAULT_SENDER'] = "yourmail@gmail.com"


# Translation system configuration
app.config['DATABASE_PATH'] = 'translations.db'
app.config['ORIGINAL_TEXTS_PATH'] = 'original_texts.json'

# Initialize extensions
db = SQLAlchemy(app)
babel = Babel(app)
CORS(app)
mail = Mail(app)

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(app.config['RAZORPAY_KEY_ID'], app.config['RAZORPAY_KEY_SECRET']))

# ... (Keep all your existing classes and functions the same) ...

# NEW: PDF Generation Function
def generate_ticket_pdf(booking_data):
    """Generate a PDF ticket with booking information"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=30,
        alignment=1  # Center aligned
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1e3a8a'),
        spaceAfter=12
    )
    
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    # Build the story (content)
    story = []
    
    # Title
    story.append(Paragraph("🎫 MUSEUMHUB DIGITAL TICKET", title_style))
    story.append(Spacer(1, 20))
    
    # Booking Information
    story.append(Paragraph("📋 BOOKING DETAILS", header_style))
    
    booking_info = [
        ["Booking ID:", booking_data['booking_id']],
        ["Visit Date:", booking_data['visit_date']],
        ["Total Amount:", booking_data['total_amount']],
        ["Contact:", booking_data['contact_phone']],
        ["Email:", booking_data['contact_email']]
    ]
    
    booking_table = Table(booking_info, colWidths=[2*inch, 4*inch])
    booking_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 10),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e6f2ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONT', (0, 0), (0, -1), 'Helvetica-Bold', 10),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    
    story.append(booking_table)
    story.append(Spacer(1, 20))
    
    # Visitors Information
    story.append(Paragraph("👥 VISITORS", header_style))
    
    visitor_data = [["No.", "Name", "Age"]]
    for i, visitor in enumerate(booking_data['visitors'], 1):
        visitor_data.append([str(i), visitor['name'], str(visitor['age'])])
    
    visitor_table = Table(visitor_data, colWidths=[0.5*inch, 3*inch, 1*inch])
    visitor_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ]))
    
    story.append(visitor_table)
    story.append(Spacer(1, 20))
    
    # Add-ons Information
    story.append(Paragraph("🎯 ADD-ONS & SERVICES", header_style))
    story.append(Paragraph(f"Additional Services: {booking_data['addons']}", normal_style))
    story.append(Spacer(1, 20))
    
    # Museum Information
    story.append(Paragraph("📍 MUSEUM INFORMATION", header_style))
    museum_info = [
        "• Address: 123 Culture Street, Art District, City - 560001",
        "• Operating Hours: 9:00 AM - 6:00 PM (Tuesday to Sunday)",
        "• Contact: +91 98765 43210 | info@museumhub.com",
        "• Website: www.museumhub.com"
    ]
    
    for info in museum_info:
        story.append(Paragraph(info, normal_style))
    
    story.append(Spacer(1, 20))
    
    # Important Instructions
    story.append(Paragraph("⚠️ IMPORTANT INSTRUCTIONS", header_style))
    instructions = [
        "• Please present this ticket at the museum entrance",
        "• Arrive 15 minutes before your scheduled visit time",
        "• This ticket is valid for single entry only",
        "• Ticket is non-refundable and non-transferable",
        "• Children under 5 must be accompanied by an adult",
        "• Photography may be restricted in certain areas",
        "• Food and drinks are not allowed in exhibition areas"
    ]
    
    for instruction in instructions:
        story.append(Paragraph(instruction, normal_style))
    
    story.append(Spacer(1, 20))
    
    # Footer
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
        alignment=1
    )
    story.append(Paragraph("Thank you for choosing MuseumHub! We hope you enjoy your visit.", footer_style))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%d %B %Y at %H:%M:%S')}", footer_style))
    
    # Build PDF
    doc.build(story)
    
    # Get PDF content
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content

# NEW: Email Sending Function
def send_ticket_email(booking_data):
    """Send ticket PDF via email"""
    try:
        # Generate PDF ticket
        pdf_content = generate_ticket_pdf(booking_data)
        
        # Create email message
        subject = f"🎫 Your MuseumHub Ticket - {booking_data['booking_id']}"
        
        msg = Message(
            subject=subject,
            recipients=[booking_data['contact_email']],
            sender=app.config['MAIL_DEFAULT_SENDER']
        )
        
        # Email body
        msg.body = f"""
Dear Visitor,

Thank you for booking with MuseumHub! Your payment was successful and your tickets are confirmed.

📋 BOOKING SUMMARY:
• Booking ID: {booking_data['booking_id']}
• Visit Date: {booking_data['visit_date']}
• Total Amount: {booking_data['total_amount']}
• Number of Visitors: {len(booking_data['visitors'])}

👥 VISITORS:
{chr(10).join([f'  • {visitor["name"]} (Age: {visitor["age"]})' for visitor in booking_data['visitors']])}

📍 MUSEUM INFORMATION:
• Address: 123 Culture Street, Art District
• Hours: 9:00 AM - 6:00 PM (Tuesday to Sunday)
• Contact: +91 98765 43210

⚠️ IMPORTANT:
• Please bring this ticket (digital or printed) and a valid ID
• Arrive 15 minutes before your visit time
• Present the ticket at the entrance

For any queries, contact us at +91 98765 43210 or info@museumhub.com

We look forward to welcoming you!

Best regards,
MuseumHub Team
www.museumhub.com
"""
        
        # HTML version of email
        msg.html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: linear-gradient(135deg, #1e3a8a, #3730a3); color: white; padding: 20px; text-align: center; border-radius: 10px; }}
        .content {{ padding: 20px; }}
        .booking-details {{ background: #f8fafc; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .visitor-list {{ background: white; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; }}
        .footer {{ background: #1e3a8a; color: white; padding: 15px; text-align: center; border-radius: 10px; margin-top: 20px; }}
        .highlight {{ color: #1e3a8a; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎫 MuseumHub Ticket Confirmation</h1>
        <p>Your museum adventure awaits!</p>
    </div>
    
    <div class="content">
        <p>Dear Visitor,</p>
        <p>Thank you for booking with MuseumHub! Your payment was successful and your tickets are confirmed.</p>
        
        <div class="booking-details">
            <h3>📋 Booking Summary</h3>
            <p><span class="highlight">Booking ID:</span> {booking_data['booking_id']}</p>
            <p><span class="highlight">Visit Date:</span> {booking_data['visit_date']}</p>
            <p><span class="highlight">Total Amount:</span> {booking_data['total_amount']}</p>
            <p><span class="highlight">Number of Visitors:</span> {len(booking_data['visitors'])}</p>
        </div>
        
        <div class="visitor-list">
            <h3>👥 Visitors</h3>
            <ul>
                {"".join([f'<li>{visitor["name"]} (Age: {visitor["age"]})</li>' for visitor in booking_data['visitors']])}
            </ul>
        </div>
        
        <h3>📍 Museum Information</h3>
        <p><strong>Address:</strong> 123 Culture Street, Art District</p>
        <p><strong>Hours:</strong> 9:00 AM - 6:00 PM (Tuesday to Sunday)</p>
        <p><strong>Contact:</strong> +91 98765 43210</p>
        
        <h3>⚠️ Important Instructions</h3>
        <ul>
            <li>Please bring this ticket (digital or printed) and a valid ID</li>
            <li>Arrive 15 minutes before your visit time</li>
            <li>Present the ticket at the entrance</li>
            <li>Food and drinks are not allowed in exhibition areas</li>
        </ul>
        
        <p>For any queries, contact us at +91 98765 43210 or info@museumhub.com</p>
        
        <p>We look forward to welcoming you!</p>
    </div>
    
    <div class="footer">
        <p><strong>MuseumHub Team</strong></p>
        <p>www.museumhub.com | +91 98765 43210</p>
    </div>
</body>
</html>
"""
        
        # Attach PDF
        msg.attach(
            filename=f"museum_ticket_{booking_data['booking_id']}.pdf",
            content_type="application/pdf",
            data=pdf_content
        )
        
        # Send email
        mail.send(msg)
        print(f"Ticket email sent successfully to {booking_data['contact_email']}")
        return True
        
    except Exception as e:
        print(f"Error sending ticket email: {str(e)}")
        return False

# NEW: Email Ticket Endpoint
@app.route('/send-ticket-email', methods=['POST'])
def send_ticket_email_route():
    """Endpoint to send ticket via email"""
    try:
        data = request.get_json()
        
        # Extract booking data from request
        booking_data = {
            'booking_id': data.get('booking_id', 'MUS000001'),
            'visit_date': data.get('visit_date', 'Not specified'),
            'total_amount': data.get('total_amount', '₹0'),
            'contact_phone': data.get('contact_phone', 'Not provided'),
            'contact_email': data.get('contact_email'),
            'visitors': data.get('visitors', []),
            'addons': data.get('addons', 'None')
        }
        
        # Validate email
        if not booking_data['contact_email']:
            return jsonify({
                'success': False,
                'message': 'Email address is required to send the ticket.'
            }), 400
        
        # Send email
        email_sent = send_ticket_email(booking_data)
        
        if email_sent:
            return jsonify({
                'success': True,
                'message': f'Ticket sent successfully to {booking_data["contact_email"]}'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to send email. Please try again.'
            }), 500
            
    except Exception as e:
        print(f"Error in send-ticket-email endpoint: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'Internal server error. Please try again later.'
        }), 500

# ... (Keep all your existing routes the same) ...



# Language mapping
LANGUAGE_CODES = {
    'en': 'en',
    'ka': 'ka',
    'hn': 'hn',
    'fn': 'fn'
}

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    tickets = db.relationship('Ticket', backref='user', lazy=True)

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Translation System Classes
class TextManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.lock = Lock()
        self._init_file()
    
    def _init_file(self):
        """Initialize the original texts file"""
        if not os.path.exists(self.file_path):
            with self.lock:
                with open(self.file_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f)
    
    def save_original_texts(self, page_url, texts):
        """Save original English texts for a page"""
        with self.lock:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            data[page_url] = texts
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get_original_texts(self, page_url):
        """Get original English texts for a page"""
        with self.lock:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get(page_url, [])

class FastTranslator:
    def __init__(self):
        self.executor = None
        
    def translate_batch_parallel(self, texts, target_lang):
        """Translate multiple texts in parallel"""
        import concurrent.futures
        
        if self.executor is None:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
            
        def translate_single(text):
            return self._translate_single(text, target_lang)
            
        # Submit all translations
        futures = [self.executor.submit(translate_single, text) for text in texts]
        
        # Collect results
        results = []
        for future in futures:
            try:
                results.append(future.result(timeout=10))
            except Exception as e:
                print(f"Translation failed: {e}")
                results.append(texts[len(results)])  # Fallback to original
                
        return results
    
    def _translate_single(self, text, target_lang):
        """Single translation with multiple fast fallbacks"""
        if not text or not text.strip() or target_lang == 'en':
            return text
            
        # Try multiple translation services
        translators = [
            self._translate_libre,
        ]
        
        for translator in translators:
            try:
                result = translator(text, target_lang)
                if result and result.strip() and result != text:
                    return result
                time.sleep(0.1)  # Be respectful to APIs
            except Exception as e:
                print(f"Translator {translator.__name__} failed: {e}")
                continue
                
        return text
    
        

class PreTranslator:
    def __init__(self, db_path):
        self.db_path = db_path
        self.lock = Lock()
        self.fast_translator = FastTranslator()
        self.text_manager = TextManager(app.config['ORIGINAL_TEXTS_PATH'])
        self._init_db()
    
    def _init_db(self):
        """Initialize the SQLite database"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS translations (
                    text_hash TEXT PRIMARY KEY,
                    original_text TEXT,
                    target_lang TEXT,
                    translated_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index for faster lookups
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_hash_lang 
                ON translations (text_hash, target_lang)
            ''')
            conn.commit()
            conn.close()
    
    def _get_text_hash(self, text, target_lang):
        """Generate a unique hash for text + language"""
        return hashlib.md5(f"{text}_{target_lang}".encode()).hexdigest()
    
    def get_cached_translation(self, text, target_lang):
        """Get translation from cache"""
        text_hash = self._get_text_hash(text, target_lang)
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT translated_text FROM translations WHERE text_hash = ?',
                (text_hash,)
            )
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
    
    def cache_translation(self, text, target_lang, translated_text):
        """Cache a translation"""
        if not text or not translated_text or text == translated_text:
            return
            
        text_hash = self._get_text_hash(text, target_lang)
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                'INSERT OR REPLACE INTO translations (text_hash, original_text, target_lang, translated_text) VALUES (?, ?, ?, ?)',
                (text_hash, text, target_lang, translated_text)
            )
            conn.commit()
            conn.close()
    
    def translate_batch(self, texts, target_lang, page_url):
        """Translate a batch of texts with caching"""
        if target_lang == 'en':
            # Return to English - get original texts
            original_texts = self.text_manager.get_original_texts(page_url)
            if original_texts and len(original_texts) == len(texts):
                return original_texts
            else:
                return texts
        
        # Save original English texts if not already saved
        current_originals = self.text_manager.get_original_texts(page_url)
        if not current_originals:
            self.text_manager.save_original_texts(page_url, texts)
        
        start_time = time.time()
        results = []
        to_translate = []
        
        # Check cache first
        for text in texts:
            if not text or not text.strip():
                results.append(text)
                continue
                
            cached = self.get_cached_translation(text, target_lang)
            if cached:
                results.append(cached)
            else:
                results.append(None)
                to_translate.append(text)
        
        # Translate missing texts in parallel
        if to_translate:
            print(f"Translating {len(to_translate)} texts to {target_lang}...")
            translated = self.fast_translator.translate_batch_parallel(to_translate, target_lang)
            
            # Cache new translations
            for original, translated_text in zip(to_translate, translated):
                if translated_text and translated_text != original:
                    self.cache_translation(original, target_lang, translated_text)
            
            # Fill in results
            translate_index = 0
            for i in range(len(results)):
                if results[i] is None:
                    results[i] = translated[translate_index]
                    translate_index += 1
        
        end_time = time.time()
        print(f"Batch translation completed in {end_time - start_time:.2f} seconds")
        
        return results

# Initialize the translator
pre_translator = PreTranslator(app.config['DATABASE_PATH'])

# Babel locale selector
def get_locale():
    return session.get('locale', 'en')

babel.init_app(app, locale_selector=get_locale)

@app.context_processor
def inject_get_locale():
    return dict(get_locale=get_locale)

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/gallery')
def gallery():
    return render_template('gallery.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        return "Thank you for your message!"  
    return render_template('contact.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('book_ticket'))
        else:
            return "Login failed"
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/book_ticket', methods=['GET', 'POST'])
def book_ticket():
    if request.method == 'POST':
        age = int(request.form['age'])
        if age < 18:
            return "You must be 18 or older to book a ticket."
        ticket = Ticket(
            name=request.form['name'],
            age=age,
            email=request.form['email'],
            user_id=session['user_id']
        )
        db.session.add(ticket)
        db.session.commit()
        return redirect(url_for('payment', ticket_id=ticket.id))
    return render_template('book_ticket.html')

@app.route('/view')
def view_exhibits():
    return render_template('view.html')

@app.route('/my_tickets')
def my_tickets():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    username = session.get('username', 'Guest')
    
    tickets = Ticket.query.filter_by(user_id=user_id).all()
    
    formatted_tickets = []
    for ticket in tickets:
        base_amount = 100
        if ticket.age < 12:
            amount = base_amount * 0.5
        elif ticket.age >= 60:
            amount = base_amount * 0.7
        else:
            amount = base_amount
        
        formatted_ticket = {
            'id': ticket.id,
            'booking_id': f'MUS24{ticket.id:04d}',
            'name': ticket.name,
            'age': ticket.age,
            'email': ticket.email,
            'amount': amount,
            'visit_date': datetime.now().strftime("%d %B %Y"),
            'status': 'active',
            'contact': session.get('phone', '+91 98765 43210'),
            'addons': 'None'
        }
        formatted_tickets.append(formatted_ticket)
    
    return render_template('my_tickets.html', tickets=formatted_tickets, username=username)

@app.route('/delete_ticket/<int:ticket_id>', methods=['POST'])
def delete_ticket(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=session['user_id']).first()
    if ticket:
        db.session.delete(ticket)
        db.session.commit()
    return redirect(url_for('my_tickets'))

# Translation System Routes
@app.route('/set-language/<lang>')
def set_language(lang):
    if lang in LANGUAGE_CODES:
        session['language'] = lang
        session.permanent = True
    return jsonify({'status': 'success', 'language': lang})

@app.route('/translate', methods=['POST'])
def translate():
    try:
        start_time = time.time()
        
        data = request.get_json()
        texts = data.get('texts', [])
        target_lang = data.get('lang', 'en')
        page_url = data.get('page_url', request.referrer or '/')
        
        if target_lang == 'en':
            return jsonify({'translations': texts})
        
        translated_texts = pre_translator.translate_batch(texts, LANGUAGE_CODES[target_lang], page_url)
        
        end_time = time.time()
        print(f"Translated {len(texts)} texts in {end_time - start_time:.2f} seconds")
        
        return jsonify({'translations': translated_texts})
    
    except Exception as e:
        print(f"Translation endpoint error: {e}")
        return jsonify({'translations': texts, 'error': str(e)}), 500

@app.route('/get-language')
def get_language():
    current_lang = session.get('language', 'en')
    return jsonify({'language': current_lang})

@app.route('/save-original-texts', methods=['POST'])
def save_original_texts():
    """Save original English texts for a page"""
    try:
        data = request.get_json()
        page_url = data.get('page_url')
        texts = data.get('texts', [])
        
        pre_translator.text_manager.save_original_texts(page_url, texts)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

# Payment Routes
@app.route('/payment/<int:ticket_id>', methods=['GET', 'POST'])
def payment(ticket_id):
    if request.method == 'GET':
        ticket = Ticket.query.get_or_404(ticket_id)
        
        base_amount = 100
        if ticket.age < 12:
            amount = base_amount * 0.5
        elif ticket.age >= 60:
            amount = base_amount * 0.7
        else:
            amount = base_amount
        
        event_date = datetime.now().strftime("%Y-%m-%d")
        
        return render_template('payment.html', 
                             ticket_id=ticket_id,
                             ticket=ticket,
                             amount=amount,
                             event_date=event_date,
                             customer_name=ticket.name,
                             customer_email=ticket.email,
                             razorpay_key=app.config['RAZORPAY_KEY_ID'])
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            razorpay_payment_id = data.get('razorpay_payment_id')
            razorpay_order_id = data.get('razorpay_order_id')
            razorpay_signature = data.get('razorpay_signature')
            amount = data.get('amount')
            
            # In a real application, verify the payment signature
            # For now, assume payment is successful
            
            return jsonify({
                'success': True,
                'payment_id': razorpay_payment_id,
                'message': 'Payment successful'
            })
            
        except Exception as e:
            print(f"Payment error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Payment processing failed. Please try again.'
            }), 400

@app.route('/create_order', methods=['POST'])
def create_order():
    """Create Razorpay order for payment"""
    try:
        data = request.get_json()
        amount = int(float(data.get('amount', 0)) * 100)
        
        if amount <= 0:
            return jsonify({'error': 'Invalid amount'}), 400
        
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'payment_capture': '1'
        }
        
        order = razorpay_client.order.create(data=order_data)
        
        return jsonify({
            'success': True,
            'order_id': order['id'],
            'amount': order['amount'],
            'currency': order['currency']
        })
        
    except Exception as e:
        print(f"Order creation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to create order'
        }), 400

@app.route('/create_payment_link', methods=['POST'])
def create_payment_link():
    data = request.json
    amount = int(data.get("amount", 0)) * 100
    name = data.get("name", "Guest")
    email = data.get("email", "")
    phone = data.get("phone", "")

    if amount <= 0:
        return jsonify({"error": "Invalid amount"}), 400

    payment_link = razorpay_client.payment_link.create({
        "amount": amount,
        "currency": "INR",
        "description": "Museum Ticket Booking",
        "customer": {
            "name": name,
            "email": email,
            "contact": phone
        },
        "notify": {"sms": True, "email": True},
        "callback_url": "http://localhost:5000/payment_success",
        "callback_method": "get"
    })

    return jsonify({"short_url": payment_link["short_url"]})

@app.route('/payment_success')
def payment_success():
    return "<h2>✅ Payment successful — Your booking is confirmed!</h2>"

# Other Routes
@app.route('/set_locale/<locale>')
def set_locale(locale):
    session['locale'] = locale
    return redirect(request.referrer)

@app.route('/test_locale')
def test_locale():
    return f"Current locale: {get_locale()}"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if request.method == 'POST':
        data = request.get_json()
        user_message = data.get('message')
        # You'll need to implement or import get_chatbot_response function
        bot_response = "Chatbot response placeholder"  # Replace with actual chatbot
        return jsonify({"response": bot_response})
    else:
        return render_template('chatbot.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('my_tickets'))

# Static file serving
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/security')
def security():
    return render_template('security.html')



if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    with app.app_context():
        db.create_all()
    
    print("Starting MuseumHub Flask Server...")
    print("Available languages: English, Kannada, Hindi, French")
    print("Server running on http://localhost:5000")
    
    app.run(debug=True)