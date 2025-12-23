import os
import json
import time
from google import genai

# --- CONFIGURATION ---
API_KEY = "PASTE_YOUR_AIza_KEY_HERE"
DATA_DIR = "processed_data"
MODEL_NAME = "gemini-flash-latest"

def repair_overlays():
    try:
        client = genai.Client(api_key=API_KEY)
    except Exception as e:
        print(f"Error: {e}")
        return

    print(f"Scanning {DATA_DIR} for overlays to repair...")

    for root, dirs, files in os.walk(DATA_DIR):
        if "coords" in root: # Only look in coordinate folders
            for file in files:
                if file.endswith(".json") and not file.endswith("_clean.json"):
                    
                    json_path = os.path.join(root, file)
                    clean_json_path = json_path.replace(".json", "_clean.json")
                    
                    # 1. Check if we already fixed this one
                    if os.path.exists(clean_json_path):
                        continue
                        
                    # 2. Find the matching "Good Text" (Gemini Output)
                    # Go up one level from 'coords' to the year folder, then into 'texts'
                    txt_dir = root.replace("coords", "texts")
                    txt_path = os.path.join(txt_dir, file.replace(".json", ".txt"))
                    
                    if not os.path.exists(txt_path):
                        print(f"Skipping {file}: No matching clean text found.")
                        continue

                    print(f"Repairing {file}...")

                    # 3. Load Data
                    with open(json_path, 'r', encoding='utf-8') as f:
                        dirty_json = f.read() # Read as string to pass to AI
                    
                    with open(txt_path, 'r', encoding='utf-8') as f:
                        clean_text = f.read()

                    # 4. The Magic Prompt
                    # We ask Gemini to merge the two data sources
                    prompt = f"""
                    I have two inputs:
                    1. A JSON list of words with coordinates (from Tesseract OCR). The text in this is full of errors.
                    2. A "Clean Text" transcript (from a better AI).

                    YOUR TASK:
                    Return the EXACT SAME JSON list, but replace the 'text' value in each object with the correct spelling from the "Clean Text".
                    
                    RULES:
                    1. DO NOT change 'x', 'y', 'w', 'h' values. Keep geometry exact.
                    2. Align the clean words to the dirty boxes as best as you can.
                    3. If Tesseract split a word (e.g. "Pos" "tal"), merge them into one box if possible, or put the full word in the first box.
                    4. Output ONLY valid JSON. No markdown formatting.

                    --- DIRTY JSON (Source of Truth for Coordinates) ---
                    {dirty_json}

                    --- CLEAN TEXT (Source of Truth for Spelling) ---
                    {clean_text}
                    """

                    try:
                        response = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=prompt,
                            config=genai.types.GenerateContentConfig(
                                response_mime_type="application/json" # Force JSON output
                            )
                        )
                        
                        # 5. Save the Clean JSON
                        if response.text:
                            # Verify it parses
                            fixed_data = json.loads(response.text)
                            
                            with open(clean_json_path, 'w', encoding='utf-8') as f:
                                json.dump(fixed_data, f, indent=2)
                            
                            print(f"   -> Fixed! Saved to {clean_json_path}")
                        
                        time.sleep(4) # Rate limit safety

                    except Exception as e:
                        print(f"   -> Failed to repair: {e}")
                        if "429" in str(e):
                            print("   -> Rate limit hit. Sleeping 60s...")
                            time.sleep(60)

if __name__ == "__main__":
    repair_overlays()