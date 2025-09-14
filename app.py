from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
import os, json, datetime
import PyPDF2
import pdfplumber
from PIL import Image
import io
import base64
from werkzeug.utils import secure_filename

app = Flask(__name__)

# ===================== File Paths =====================
HISTORY_FILE = "chat_history.json"
USER_DATA_FILE = "user_data.json"
LOG_FILE = "chat_log.txt"
PDF_UPLOAD_FOLDER = "uploads"
PDF_DATA_FILE = "pdf_data.json"

# Create uploads directory if it doesn't exist
os.makedirs(PDF_UPLOAD_FOLDER, exist_ok=True)

# PDF configuration
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

# ===================== Helper Functions =====================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"profile": {}, "appointments": [], "emergency": [], "medications": []}
    return {"profile": {}, "appointments": [], "emergency": [], "medications": []}

def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ===================== PDF Helper Functions =====================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_pdf_data():
    if os.path.exists(PDF_DATA_FILE):
        try:
            with open(PDF_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_pdf_data(data):
    with open(PDF_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def extract_text_from_pdf(file_path):
    """Extract text from PDF using multiple methods for better accuracy"""
    text = ""
    
    # Method 1: Using pdfplumber (better for complex layouts)
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        print(f"pdfplumber failed: {e}")
    
    # Method 2: Using PyPDF2 (fallback)
    if not text.strip():
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            print(f"PyPDF2 failed: {e}")
    
    return text.strip()

def analyze_pdf_with_ai(text, filename):
    """Use Gemini AI to analyze PDF content"""
    try:
        prompt = f"""
        Analyze this PDF document titled "{filename}" and provide:
        
        1. Document Summary (2-3 sentences)
        2. Key Topics/Themes
        3. Important Information/Findings
        4. Document Type (e.g., medical report, research paper, invoice, etc.)
        5. Action Items (if any)
        6. Health-related insights (if applicable)
        
        PDF Content:
        {text[:4000]}  # Limit to first 4000 characters to avoid token limits
        
        Please format your response clearly with headers for each section.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error analyzing document: {str(e)}"

# ===================== AI Setup =====================
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("⚠️ GOOGLE_API_KEY is not set.")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

chat = model.start_chat(history=[])

# ===================== Routes =====================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    user_input = request.json.get("message", "")
    if not user_input.strip():
        return jsonify({"reply": "⚠️ Please enter a message."})

    try:
        response = chat.send_message(user_input)
        bot_text = getattr(response, "text", "") or getattr(response, "last", "")

        history = load_history()
        history.append({"user": user_input, "bot": bot_text})
        save_history(history)

        with open(LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"[{datetime.datetime.now()}]\nYou: {user_input}\nHealthBot: {bot_text}\n\n")

    except Exception as e:
        bot_text = f"Sorry, something went wrong: {e}"

    return jsonify({"reply": bot_text})

@app.route("/get_history", methods=["GET"])
def get_history():
    return jsonify(load_history())

@app.route("/edit_message/<int:index>", methods=["PUT"])
def edit_message(index):
    history = load_history()
    if 0 <= index < len(history):
        new_message = request.json.get("message", "")
        if not new_message.strip():
            return jsonify({"status": "error", "message": "Message cannot be empty"}), 400

        try:
            response = chat.send_message(new_message)
            bot_text = getattr(response, "text", "") or getattr(response, "last", "")
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

        history[index] = {"user": new_message, "bot": bot_text}
        save_history(history)
        return jsonify({"status": "success", "reply": bot_text})
    return jsonify({"status": "error", "message": "Message not found"}), 404

@app.route("/delete_message/<int:index>", methods=["DELETE"])
def delete_message(index):
    history = load_history()
    if 0 <= index < len(history):
        history.pop(index)
        save_history(history)
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Message not found"}), 404

@app.route("/clear_chat", methods=["DELETE"])
def clear_chat():
    save_history([])
    return jsonify({"status": "success", "message": "Chat cleared!"})

# ===================== Profile, Medications, Emergency =====================
@app.route("/get_user_data", methods=["GET"])
def get_user_data():
    return jsonify(load_user_data())

@app.route("/save_profile", methods=["POST"])
def save_profile():
    data = load_user_data()
    profile_data = request.json
    profile_data['custom_fields'] = profile_data.get('custom_fields', [])
    data["profile"] = profile_data
    save_user_data(data)
    return jsonify({"status": "success", "message": "Profile saved!", "data": profile_data})

@app.route("/save_medication", methods=["POST"])
def save_medication():
    data = load_user_data()
    medication = request.json
    if "medications" not in data:
        data["medications"] = []
    data["medications"].append(medication)
    save_user_data(data)
    return jsonify({"status": "success", "message": "Medication added!"})

@app.route("/delete_medication/<int:index>", methods=["DELETE"])
def delete_medication(index):
    data = load_user_data()
    if 0 <= index < len(data.get("medications", [])):
        data["medications"].pop(index)
        save_user_data(data)
        return jsonify({"status": "success", "message": "Medication deleted."})
    return jsonify({"status": "error", "message": "Medication not found."}), 404

@app.route("/save_emergency_contact", methods=["POST"])
def save_emergency_contact():
    data = load_user_data()
    contact = request.json
    if "emergency_contacts" not in data:
        data["emergency_contacts"] = []
    data["emergency_contacts"].append(contact)
    save_user_data(data)
    return jsonify({"status": "success", "message": "Emergency contact added!"})

@app.route("/delete_emergency_contact/<int:index>", methods=["DELETE"])
def delete_emergency_contact(index):
    data = load_user_data()
    if 0 <= index < len(data.get("emergency_contacts", [])):
        data["emergency_contacts"].pop(index)
        save_user_data(data)
        return jsonify({"status": "success", "message": "Emergency contact deleted."})
    return jsonify({"status": "error", "message": "Emergency contact not found."}), 404

# ===================== PDF Reader Routes =====================
@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"status": "error", "message": "Only PDF files are allowed"}), 400
    
    # Check file size
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({"status": "error", "message": "File too large. Maximum size is 16MB"}), 400
    
    try:
        # Save file
        filename = secure_filename(file.filename)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(PDF_UPLOAD_FOLDER, unique_filename)
        file.save(file_path)
        
        # Extract text
        extracted_text = extract_text_from_pdf(file_path)
        if not extracted_text:
            os.remove(file_path)  # Clean up if no text extracted
            return jsonify({"status": "error", "message": "Could not extract text from PDF"}), 400
        
        # Analyze with AI
        ai_analysis = analyze_pdf_with_ai(extracted_text, filename)
        
        # Save PDF data
        pdf_data = load_pdf_data()
        pdf_info = {
            "id": len(pdf_data),
            "filename": filename,
            "unique_filename": unique_filename,
            "file_path": file_path,
            "upload_date": datetime.datetime.now().isoformat(),
            "file_size": file_size,
            "extracted_text": extracted_text,
            "ai_analysis": ai_analysis,
            "summary": ai_analysis.split('\n')[0] if ai_analysis else "No summary available"
        }
        
        pdf_data.append(pdf_info)
        save_pdf_data(pdf_data)
        
        return jsonify({
            "status": "success", 
            "message": "PDF uploaded and analyzed successfully!",
            "pdf_info": pdf_info
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error processing PDF: {str(e)}"}), 500

@app.route("/get_pdfs", methods=["GET"])
def get_pdfs():
    pdf_data = load_pdf_data()
    # Return only essential info for the list view
    pdf_list = []
    for pdf in pdf_data:
        pdf_list.append({
            "id": pdf["id"],
            "filename": pdf["filename"],
            "upload_date": pdf["upload_date"],
            "file_size": pdf["file_size"],
            "summary": pdf["summary"]
        })
    return jsonify(pdf_list)

@app.route("/get_pdf/<int:pdf_id>", methods=["GET"])
def get_pdf(pdf_id):
    pdf_data = load_pdf_data()
    if 0 <= pdf_id < len(pdf_data):
        return jsonify(pdf_data[pdf_id])
    return jsonify({"status": "error", "message": "PDF not found"}), 404

@app.route("/delete_pdf/<int:pdf_id>", methods=["DELETE"])
def delete_pdf(pdf_id):
    pdf_data = load_pdf_data()
    if 0 <= pdf_id < len(pdf_data):
        pdf_info = pdf_data[pdf_id]
        
        # Delete file from filesystem
        try:
            if os.path.exists(pdf_info["file_path"]):
                os.remove(pdf_info["file_path"])
        except Exception as e:
            print(f"Error deleting file: {e}")
        
        # Remove from data
        pdf_data.pop(pdf_id)
        
        # Update IDs
        for i, pdf in enumerate(pdf_data):
            pdf["id"] = i
        
        save_pdf_data(pdf_data)
        return jsonify({"status": "success", "message": "PDF deleted successfully"})
    
    return jsonify({"status": "error", "message": "PDF not found"}), 404

@app.route("/ask_pdf/<int:pdf_id>", methods=["POST"])
def ask_pdf(pdf_id):
    pdf_data = load_pdf_data()
    if 0 > pdf_id or pdf_id >= len(pdf_data):
        return jsonify({"status": "error", "message": "PDF not found"}), 404
    
    user_question = request.json.get("question", "")
    if not user_question.strip():
        return jsonify({"status": "error", "message": "Please enter a question"}), 400
    
    try:
        pdf_info = pdf_data[pdf_id]
        pdf_text = pdf_info["extracted_text"]
        
        # Create context-aware prompt
        prompt = f"""
        Based on the following PDF document "{pdf_info['filename']}", please answer this question: {user_question}
        
        PDF Content:
        {pdf_text[:3000]}  # Limit content to avoid token limits
        
        Please provide a detailed and accurate answer based on the document content. If the answer cannot be found in the document, please state that clearly.
        """
        
        response = model.generate_content(prompt)
        answer = response.text
        
        return jsonify({
            "status": "success",
            "answer": answer,
            "pdf_filename": pdf_info["filename"]
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error processing question: {str(e)}"}), 500

# ===================== Run =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
