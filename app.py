from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import os
import google.generativeai as genai
from chat1 import fetch_website_content, extract_pdf_text, initialize_vector_store
from chat2 import llm, setup_retrieval_qa

app = Flask(__name__)

# Secret key for session management
app.secret_key = 'your_secret_key'

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Database & Encryption
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Database Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Encrypted
    place = db.Column(db.String(100), nullable=False)

# Create Database Tables (Run once)
with app.app_context():
    db.create_all()

# ----------------------------------------------
# ✅ User Authentication Routes
# ----------------------------------------------
@app.route('/')
def home():
    return render_template('home.html')  # Landing page with login/signup options

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        place = request.form['place']

        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Email already registered! Try logging in."

        new_user = User(name=name, email=email, password=password, place=place)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))  # Redirect to login page

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id  # Store session data
            return redirect(url_for('index'))  # Redirect to chatbot page after login
        else:
            return "Invalid email or password. Try again."

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

# ----------------------------------------------
# ✅ Chatbot Integration
# ----------------------------------------------

# Paste your Gemini API Key here
API_KEY = "your_actual_api_key_here"  # Replace this with your key
genai.configure(api_key=API_KEY)

# Example URLs and PDF files
urls = ["https://mospi.gov.in/4-agricultural-statistics"]
pdf_files = [
    r"C:\\Users\\haduj\\OneDrive\\Desktop\\GSC pro\\AgriGenius-main\\Data\\Farming Schemes.pdf",
    r"C:\\Users\\haduj\\OneDrive\\Desktop\\GSC pro\\AgriGenius-main\\Data\\farmerbook.pdf"
]

# Ensure PDFs exist before extracting text
pdf_texts = []
for pdf in pdf_files:
    if os.path.exists(pdf):
        pdf_texts.append(extract_pdf_text(pdf))
    else:
        print(f"Warning: File not found - {pdf}")

# Fetch content from websites
website_contents = [fetch_website_content(url) for url in urls]

# Combine all content into chunks
all_contents = website_contents + pdf_texts

# Initialize the vector store
db_vector = initialize_vector_store(all_contents)

# Set up the RetrievalQA chain
chain = setup_retrieval_qa(db_vector)

# Predefined responses
predefined_responses = {
    "who developed you?": "I was developed by Jayesh Bhandarkar.",
    "who created you?": "I was created by Jayesh Bhandarkar.",
    "who made you?": "I was made by Jayesh Bhandarkar.",

    # Farming-related questions
    "what is organic farming?": "Organic farming is a method of using natural fertilizers and avoiding synthetic chemicals.",
    "how can i increase crop yield?": "Improve soil health, use high-quality seeds, practice crop rotation, and apply organic fertilizers.",
    "what is crop rotation?": "A farming practice where different crops are planted in succession on the same land to improve soil fertility.",
    "what is drip irrigation?": "A water-efficient irrigation method that delivers water directly to plant roots.",
    "how to control pests naturally?": "Use neem oil, companion planting, and natural predators like ladybugs.",
    "how does climate change affect agriculture?": "It impacts rainfall patterns, increases droughts, and affects crop growth cycles.",
    "what is mulching?": "Covering soil with organic/inorganic material to retain moisture and suppress weeds.",
    "how to test soil quality?": "Use a soil testing kit to check pH, nutrients, and organic matter content.",

    # Soil and Crop Information in Kakinada
    "what are the soil types in kakinada?": "Kakinada has lateritic, deltaic alluvial, coastal sandy, and clayey soils.",
}

@app.route('/index')
def index():
    if 'user_id' in session:
        return render_template('index.html')  # Chatbot page
    return redirect(url_for('login'))  # Redirect to login if not logged in

@app.route('/ask', methods=['POST'])
def ask():
    if 'user_id' not in session:
        return jsonify({"answer": "Please log in to access the chatbot."})

    query = request.form['messageText'].strip().lower()

    # Check predefined responses first
    if query in predefined_responses:
        return jsonify({"answer": predefined_responses[query]})

    # If no predefined response, use the Gemini LLM
    try:
        response = chain.invoke({"query": query})  # Use `.invoke()` for Gemini
        return jsonify({"answer": response['result']})
    except Exception as e:
        print("Error:", e)
        return jsonify({"answer": "Sorry, there was an error processing your request."})

if __name__ == "__main__":
    app.run(debug=True)
