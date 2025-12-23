import os
import json
import cv2
import pytesseract
from pytesseract import Output

# --- CONFIGURATION ---
DATA_DIR = "processed_data"
# If Tesseract is not in your PATH, uncomment and set the line below:
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def generate_json_map():
    print(f"Scanning {DATA_DIR} for images...")
    
    count = 0
    for root, dirs, files in os.walk(DATA_DIR):
        for file in files:
            if file.lower().endswith((".jpg", ".png")):
                img_path = os.path.join(root, file)
                
                # We save the JSON map in a 'coords' folder next to 'images'
                # Example: processed_data/IPG/1869/coords/page_001.json
                coords_dir = root.replace("images", "coords")
                os.makedirs(coords_dir, exist_ok=True)
                
                json_path = os.path.join(coords_dir, file.rsplit('.', 1)[0] + ".json")
                
                # Skip if already exists to save time
                if os.path.exists(json_path):
                    continue
                    
                print(f"Mapping coordinates for: {file}...")
                
                try:
                    img = cv2.imread(img_path)
                    # Get word-level bounding boxes
                    d = pytesseract.image_to_data(img, output_type=Output.DICT)
                    
                    word_list = []
                    n_boxes = len(d['text'])
                    
                    for i in range(n_boxes):
                        # Filter out empty noise and low confidence garbage
                        if int(d['conf'][i]) > 0 and d['text'][i].strip() != "":
                            word_list.append({
                                "text": d['text'][i],
                                "x": d['left'][i],
                                "y": d['top'][i],
                                "w": d['width'][i],
                                "h": d['height'][i]
                            })
                    
                    # Save to JSON
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(word_list, f)
                    
                    count += 1
                        
                except Exception as e:
                    print(f"Error processing {file}: {e}")

    print(f"Done! Generated coordinate maps for {count} pages.")

if __name__ == "__main__":
    generate_json_map()