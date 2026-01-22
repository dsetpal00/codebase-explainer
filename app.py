import os
import io
import zipfile
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# -----------------------------
# 🔐 SECURE API KEY LOADING
# -----------------------------
def load_env_file():
    try:
        with open('.env', 'r') as f:
            for line in f:
                if line.startswith('API_KEY='):
                    return line.split('=', 1)[1].strip()
    except FileNotFoundError:
        pass
    return None

API_KEY = load_env_file()
if not API_KEY:
    raise ValueError("API_KEY not found in .env file.")

genai.configure(api_key=API_KEY)

# -----------------------------
# 🤖 DYNAMIC MODEL SELECTION (Optimized for Quota)
# -----------------------------
# -----------------------------
# 🤖 DYNAMIC MODEL SELECTION (Fixed for 2026)
# -----------------------------
def get_best_model():
    print("--- Attempting to find Gemini Models ---")
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        print(f"Found {len(available_models)} compatible models.")

        # Updated Priority: 2.5 is current, 2.0 is stable, 1.5-latest is fallback
        priority_list = [
            'gemini-2.5-flash', 
            'gemini-2.0-flash', 
            'gemini-1.5-flash-latest'
        ]

        for target in priority_list:
            for m_name in available_models:
                if target in m_name:
                    print(f"🎯 MATCH FOUND: {m_name}")
                    return genai.GenerativeModel(model_name=m_name)
        
        # If nothing in the list matches, use the first available model found
        if available_models:
            print(f"⚠️ No preferred models found. Using first available: {available_models[0]}")
            return genai.GenerativeModel(available_models[0])

        # Absolute last resort manual fallback (using -latest alias)
        return genai.GenerativeModel('gemini-1.5-flash-latest')

    except Exception as e:
        print(f"❌ API LIST ERROR: {e}")
        # Use the alias here as well to avoid the 404
        return genai.GenerativeModel('gemini-1.5-flash-latest')
# Initialize the model
model = get_best_model()

# -----------------------------
# 🛠️ HYBRID INPUT LOGIC
# -----------------------------
def process_input(request):
    combined_content = request.form.get("code", "")
    if 'code_file' in request.files:
        file = request.files['code_file']
        if file.filename.endswith('.zip'):
            try:
                with zipfile.ZipFile(io.BytesIO(file.read())) as z:
                    for name in z.namelist():
                        if name.endswith(('.py', '.js', '.ts', '.java', '.html', '.css')):
                            with z.open(name) as f:
                                combined_content += f"\n\n--- FILE: {name} ---\n{f.read().decode('utf-8', errors='ignore')}"
            except: pass
        elif file.filename != '':
            combined_content += f"\n\n--- FILE: {file.filename} ---\n{file.read().decode('utf-8', errors='ignore')}"
    return combined_content

def generate(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text if response and response.text else ""
    except Exception as e:
        return f"AI Error: {str(e)}"

# -----------------------------
# ✂️ PARSING HELPER
# -----------------------------
def extract_section(text, start_tag, end_tag):
    try:
        if start_tag not in text: return "Content not generated."
        start = text.find(start_tag) + len(start_tag)
        if end_tag == "END": return text[start:].strip()
        end = text.find(end_tag)
        return text[start:end].strip() if end != -1 else text[start:].strip()
    except:
        return "Parsing error."

# -----------------------------
# 🌐 ROUTES
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        code = process_input(request)
        docs = request.form.get("docs", "")
        old_code = request.form.get("old_code", "")
        question = request.form.get("question", "")

        if not code.strip():
            return jsonify({"error": "No code detected."}), 400

        # --- THE MASTER PROMPT (Saves Quota by making 1 call instead of 4) ---
       
    # --- THE BULLETPROOF MASTER PROMPT ---
       # --- THE BULLETPROOF MASTER PROMPT ---
        master_prompt = f"""
        Analyze this code using these docs as context: {docs}
        
        CODE:
        {code}
        
        Provide the following sections EXACTLY in this format with the tags:
        [BIG_PICTURE]
        (Exactly 3 bullet points)

        [WHY_EXISTS]
        (Exactly 2 sentences)

        [TRAPS]
        (Top 3 risks with ⚠️)

        [MERMAID]
        graph TD
          %% Define Styles
          classDef logic fill:#eff6ff,stroke:#2563eb,stroke-width:2px,color:#1e40af;
          classDef UI fill:#fff7ed,stroke:#ea580c,stroke-width:2px,color:#9a3412;
          classDef data fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#166534;
          classDef alert fill:#fef2f2,stroke:#dc2626,stroke-width:2px,color:#991b1b;

          %% CRITICAL RULES FOR VISUAL CLARITY:
          %% 1. Use double quotes for ALL labels: ID["Label Text"]
          %% 2. MANDATORY: Break long text with <br/> inside quotes. Example: A["User clicks<br/>Submit Button"]
          %% 3. Keep node labels under 4 words per line.
          %% 4. Use subgraphs to group related functions.
          %% 5. Avoid crossing lines where possible.

          (Insert Colorful Mermaid Logic Here)
        """

        full_analysis = generate(master_prompt)

        # Splitting the master response into the UI boxes
        result = {
            "big_picture": extract_section(full_analysis, "[BIG_PICTURE]", "[WHY_EXISTS]"),
            "why_this_exists": extract_section(full_analysis, "[WHY_EXISTS]", "[TRAPS]"),
            "hidden_traps": extract_section(full_analysis, "[TRAPS]", "[MERMAID]"),
            "flow": extract_section(full_analysis, "[MERMAID]", "END")
        }

        # Separate calls only for optional, specific interactions
        if question.strip():
            result["mentor_answer"] = generate(f"Question: {question}\nContext: {code}\nAnswer in one short mentor-like paragraph.")
        
        if old_code.strip():
            result["backward_compatibility"] = generate(f"Compare OLD vs NEW for breaking changes.\nOLD: {old_code}\nNEW: {code}\nOutput Safety Score 0-100 and list breaks.")

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)