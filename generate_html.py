import os
import time
import math
import concurrent.futures
from google import genai
import PIL.Image

# --- CONFIGURATION ---
KEY_FILE = "keys.txt"
DATA_DIR = "processed_data"
MODEL_NAME = "gemini-3-flash-preview"

# MASTER STYLESHEET (Same as before)
CSS_TEMPLATE = """
<style>
    body { 
        font-family: 'Georgia', 'Times New Roman', serif; 
        background-color: #fdfbf7; 
        color: #1a1a1a; 
        line-height: 1.4;
        padding: 40px;
        max-width: 800px;
        margin: auto;
        box-shadow: 0 0 20px rgba(0,0,0,0.1);
    }
    h1, h2, h3 { text-align: center; text-transform: uppercase; font-weight: normal; letter-spacing: 2px; margin-bottom: 30px; }
    h1 { font-size: 24px; border-bottom: 2px double black; padding-bottom: 10px; }
    h2 { font-size: 18px; }
    p { margin-bottom: 15px; text-align: justify; }
    table { width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; border: 2px solid black; }
    th { border: 1px solid black; padding: 8px; text-transform: uppercase; font-size: 12px; background: #eee; }
    td { border: 1px solid black; padding: 8px; vertical-align: top; }
    .center { text-align: center; }
    .right { text-align: right; }
    .small { font-size: 12px; }
    .bold { font-weight: bold; }
    .italic { font-style: italic; }
    hr { border: 0; border-top: 1px solid black; margin: 20px 0; }
</style>
"""

def load_keys(filepath):
    keys = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if parts:
                    keys.append(parts[0])
        return keys
    except FileNotFoundError:
        print("CRITICAL: keys.txt not found!")
        exit()

def process_batch(worker_id, api_key, file_list):
    """
    This function runs inside a separate thread.
    It acts like an independent program using ONE specific key.
    """
    print(f"   [Worker {worker_id}] Started! Assigned {len(file_list)} pages.")
    
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"   [Worker {worker_id}] Key Error: {e}")
        return

    prompt = """
    Look at this image of a 19th-century postal guide.
    Reproduce it EXACTLY as an HTML web page.
    RULES:
    1. Do not include <html>, <head>, or <body> tags. Just give the inner content.
    2. Use semantic tags: <h1>, <table>, <p>.
    3. Use classes: 'center', 'right', 'bold', 'italic', 'small'.
    4. Transcribe spelling EXACTLY.
    5. OUTPUT FORMAT: HTML code only.
    """

    for img_path, html_path, filename in file_list:
        # Double check if done (in case another thread somehow touched it, though unlikely)
        if os.path.exists(html_path):
            continue

        print(f"   [Worker {worker_id}] Processing: {filename}...")
        
        try:
            image = PIL.Image.open(img_path)
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[image, prompt]
            )
            
            if response.text:
                full_html = f"<!DOCTYPE html><html><head><meta charset='utf-8'>{CSS_TEMPLATE}</head><body>{response.text}</body></html>"
                full_html = full_html.replace("```html", "").replace("```", "")
                
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(full_html)
                print(f"   [Worker {worker_id}] -> Saved HTML.")
            
            # Rate Limit Safety: Sleep 4s PER WORKER.
            # Since workers run in parallel, this doesn't slow down the total throughput.
            time.sleep(4) 
            
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                print(f"   [Worker {worker_id}] QUOTA HIT for this key. Worker stopping.")
                break # This specific key is dead for the day. The worker retires.
            else:
                print(f"   [Worker {worker_id}] Error on {filename}: {e}")
                time.sleep(5)

def main():
    # 1. Load Keys
    keys = load_keys(KEY_FILE)
    num_workers = len(keys)
    if num_workers == 0:
        print("No keys found in keys.txt")
        return

    print(f"Found {num_workers} API Keys. Launching {num_workers} parallel threads.")

    # 2. Find all work to be done
    all_tasks = []
    print(f"Scanning {DATA_DIR} for pending images...")
    
    for root, dirs, files in os.walk(DATA_DIR):
        for file in files:
            if file.lower().endswith((".jpg", ".png")):
                img_path = os.path.join(root, file)
                html_dir = root.replace("images", "htmls")
                os.makedirs(html_dir, exist_ok=True)
                html_path = os.path.join(html_dir, file.rsplit('.', 1)[0] + ".html")
                
                if not os.path.exists(html_path):
                    all_tasks.append((img_path, html_path, file))

    total_files = len(all_tasks)
    print(f"Found {total_files} pages needing HTML generation.")

    if total_files == 0:
        print("All done! No pages left to process.")
        return

    # 3. Split work evenly among keys
    # If we have 100 files and 3 keys:
    # Batch 1 gets 34, Batch 2 gets 33, Batch 3 gets 33.
    chunk_size = math.ceil(total_files / num_workers)
    batches = []
    
    for i in range(0, total_files, chunk_size):
        batches.append(all_tasks[i : i + chunk_size])

    # 4. Launch Threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for i in range(num_workers):
            if i < len(batches): # Safety check if we have more keys than files
                # worker_id, api_key, file_list
                futures.append(executor.submit(process_batch, i+1, keys[i], batches[i]))
        
        # Wait for all to finish
        concurrent.futures.wait(futures)

    print("\nAll workers finished (or hit quota limits).")

if __name__ == "__main__":
    main()