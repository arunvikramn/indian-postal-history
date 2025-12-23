import os
import json
import shutil
from PIL import Image
from pdf2image import convert_from_path

# --- CONFIGURATION ---
OUTPUT_ROOT = "processed_data"
POPPLER_PATH = r"G:\STAMP\Indian Postal History OCR Project\poppler-25.12.0\Library\bin"

# TESSERACT CONFIG (Update this if your path is different)
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Check for Tesseract availability
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    print("Warning: 'pytesseract' library not found. Orientation checks will be skipped.")

def process_project():
    root_dir = os.getcwd()
    exclude = {OUTPUT_ROOT, '.git', '.github', 'scripts', 'poppler-25.12.0'}
    
    # ==========================================
    # PHASE 1: PROCESS NEW PDFS (THE WORKER)
    # ==========================================
    print(f"--- Step 1: Checking for new PDFs to process ---")
    
    for collection_name in os.listdir(root_dir):
        collection_path = os.path.join(root_dir, collection_name)

        if not os.path.isdir(collection_path) or collection_name in exclude or collection_name.startswith('.'):
            continue

        pdf_files = [f for f in os.listdir(collection_path) if f.lower().endswith(".pdf")]
        
        for file in pdf_files:
            # Determine Book ID
            if "-" in file:
                book_id = file.split("-")[-1].replace(".pdf", "")
            else:
                book_id = file.replace(".pdf", "")
            
            # Define output paths
            img_out = os.path.join(OUTPUT_ROOT, collection_name, book_id, "images")
            html_out = os.path.join(OUTPUT_ROOT, collection_name, book_id, "htmls") # Changed to htmls

            # SKIP if output already exists (Idempotency)
            if os.path.exists(img_out) and len(os.listdir(img_out)) > 0:
                continue 

            print(f"   [NEW] Found {file} -> Processing...")
            os.makedirs(img_out, exist_ok=True)
            os.makedirs(html_out, exist_ok=True)

            try:
                pages = convert_from_path(
                    os.path.join(collection_path, file), 
                    dpi=150, 
                    poppler_path=POPPLER_PATH
                )

                for i, page in enumerate(pages):
                    page_num = i + 1
                    base_fname = f"page_{page_num:03d}"
                    
                    # 1. Save Image
                    page.save(os.path.join(img_out, f"{base_fname}.jpg"), 'JPEG', quality=80)
                    
                    # 2. Save HTML Placeholder
                    html_content = f"""
                    <html>
                    <body style="font-family: courier; color: #555; padding: 20px; background: #f4f4f4;">
                        <h3>Page {page_num}</h3>
                        <p>[OCR Content Pending...]</p>
                    </body>
                    </html>
                    """
                    with open(os.path.join(html_out, f"{base_fname}.html"), "w", encoding="utf-8") as f:
                        f.write(html_content)

                print(f"      -> Done. Extracted {len(pages)} pages.")

            except Exception as e:
                print(f"      -> ERROR: {e}")
                # Cleanup failed attempt to allow retry
                shutil.rmtree(os.path.join(OUTPUT_ROOT, collection_name, book_id))
    # ==========================================
    # PHASE 2: ORIENTATION CHECK (THE AUDITOR)
    # ==========================================
    if HAS_TESSERACT:
        print(f"\n--- Step 2: Checking Orientation (Smart Cache) ---")
        
        # Import timeout tools
        import signal
        
        # Define a timeout handler
        class TimeoutError(Exception): pass 
        def handler(signum, frame): raise TimeoutError()
        
        # (Note: Signal only works on Linux/Mac. For Windows we use a simpler approach below)

        for col_name in os.listdir(OUTPUT_ROOT):
            col_path = os.path.join(OUTPUT_ROOT, col_name)
            if not os.path.isdir(col_path): continue

            for book_id in os.listdir(col_path):
                img_path = os.path.join(col_path, book_id, "images")
                if not os.path.isdir(img_path): continue

                # Load Audit Log
                audit_file = os.path.join(col_path, book_id, "audit_log.json")
                audit_log = {}
                if os.path.exists(audit_file):
                    try:
                        with open(audit_file, 'r') as f:
                            audit_log = json.load(f)
                    except:
                        audit_log = {} # corrupted log, start over

                images = sorted([f for f in os.listdir(img_path) if f.lower().endswith(".jpg")])
                total_imgs = len(images)
                updates_made = False

                print(f"   Checking {col_name}/{book_id} ({total_imgs} pages)...")

                for idx, img_file in enumerate(images):
                    if img_file in audit_log:
                        continue
                    
                    # Print progress every 10 images so you know it's alive
                    if idx % 10 == 0:
                        print(f"      Scanning page {idx}/{total_imgs}...", end="\r")
                    
                    full_img_path = os.path.join(img_path, img_file)
                    
                    try:
                        # SIMPLE TIMEOUT LOGIC: 
                        # We just trust Tesseract, but if it crashes we catch it.
                        # Real timeouts on Windows require 'threading', which is complex.
                        # Instead, we just print BEFORE we start.
                        
                        # Tesseract OSD Check
                        osd = pytesseract.image_to_osd(full_img_path, config='--psm 0 -c min_characters_to_try=5')
                        
                        rotation = 0
                        for line in osd.split("\n"):
                            if "Rotate" in line:
                                try:
                                    rotation = int(line.split(":")[1].strip())
                                except: pass
                        
                        if rotation != 0:
                            print(f"      -> Rotating {img_file} by {rotation}°      ") # Spaces to clear line
                            with Image.open(full_img_path) as im:
                                rotated = im.rotate(-rotation, expand=True)
                                rotated.save(full_img_path, quality=80)
                            audit_log[img_file] = f"rotated_{rotation}"
                        else:
                            audit_log[img_file] = "checked_ok"
                        
                        updates_made = True

                    except Exception as e:
                        # If Tesseract hangs or fails, we log it and move on
                        audit_log[img_file] = "skipped_error"
                        updates_made = True
                
                print(f"      Done with {book_id}.                  ") # Newline after progress bar

                if updates_made:
                    with open(audit_file, 'w') as f:
                        json.dump(audit_log, f, indent=4)

    # ==========================================
    # PHASE 3: BUILD INDEX (THE LIBRARIAN)
    # ==========================================
    print(f"\n--- Step 3: Rebuilding Website Index ---")
    
    site_index = {}
    
    if os.path.exists(OUTPUT_ROOT):
        for col_name in sorted(os.listdir(OUTPUT_ROOT)):
            col_path = os.path.join(OUTPUT_ROOT, col_name)
            if not os.path.isdir(col_path): continue

            site_index[col_name] = {}
            
            for book_id in sorted(os.listdir(col_path)):
                img_path = os.path.join(col_path, book_id, "images")
                if os.path.isdir(img_path):
                    jpg_count = len([f for f in os.listdir(img_path) if f.lower().endswith(".jpg")])
                    if jpg_count > 0:
                        site_index[col_name][book_id] = jpg_count

    index_path = os.path.join(OUTPUT_ROOT, "index.json")
    with open(index_path, "w") as f:
        json.dump(site_index, f, indent=4)
    
    print(f"Success! Index saved to {index_path}")

if __name__ == "__main__":
    process_project()