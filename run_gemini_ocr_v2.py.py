import os
import time
from google import genai
import PIL.Image

# --- CONFIGURATION ---
API_KEY = "PASTE_YOUR_AIza_KEY_HERE" 
DATA_DIR = "processed_data"
MODEL_NAME = "gemini-flash-latest"

def run_smart_ocr():
    print(f"Initializing Gemini Client with model: {MODEL_NAME}...")
    
    try:
        client = genai.Client(api_key=API_KEY)
    except Exception as e:
        print(f"CRITICAL ERROR: Could not start Client. Check your Key. Error: {e}")
        return

    # The Prompt: optimized to stop LaTeX and force Markdown tables
    prompt = """
    Transcribe this image into clean Markdown text.
    RULES:
    1. Preserve original spelling exactly (e.g., use "Mooltan", "Calcutta"). Do not modernize.
    2. If there is a table, format it as a Markdown table.
    3. STRICTLY NO LATEX or math formatting (no $ symbols, no \\rule). 
    4. If you see a horizontal divider line, just use "---".
    5. Do not describe visual ornaments like ; just skip them.
    """

    print(f"Scanning {DATA_DIR} for empty text files...")
    
    count = 0
    for root, dirs, files in os.walk(DATA_DIR):
        for file in files:
            if file.endswith(".txt"):
                txt_path = os.path.join(root, file)
                
                # RESUME LOGIC: Only process empty files
                if os.path.getsize(txt_path) == 0:
                    img_path = txt_path.replace(".txt", ".jpg").replace("texts", "images")
                    
                    if os.path.exists(img_path):
                        print(f"Processing: {file}...")
                        try:
                            image = PIL.Image.open(img_path)
                            response = client.models.generate_content(
                                model=MODEL_NAME,
                                contents=[image, prompt]
                            )
                            
                            if response.text:
                                with open(txt_path, "w", encoding="utf-8") as f:
                                    f.write(response.text)
                                print(f"   -> Success. Transcribed {len(response.text)} chars.")
                                count += 1
                            else:
                                print("   -> Warning: Gemini returned no text.")
                            
                            time.sleep(4)
                            
                        except Exception as e:
                            print(f"   -> Error: {e}")
                            if "429" in str(e): # Quota Hit
                                print("   -> Rate Limit hit. Sleeping 60s...")
                                time.sleep(60)
    print(f"\nDone! Processed {count} pages.")

if __name__ == "__main__":
    run_smart_ocr()