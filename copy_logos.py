import shutil
import os

brain_dir = r"C:\Users\Sahil Chaudhary\.gemini\antigravity\brain\33b6ee20-254c-488c-bf83-5664d9ca9aca"
img_dir = r"c:\Users\Sahil Chaudhary\Desktop\Vs Code\FaizInternet\static\img"

mapping = {
    "media__1771744042444.jpg": "faiz_logo.jpg",
    "media__1771744042222.jpg": "csc_logo.jpg",
    "media__1771744042268.jpg": "aadhaar_logo.jpg",
    "media__1771744042399.jpg": "edistrict_logo.jpg",
    "media__1771744042134.jpg": "voter_logo.jpg"
}

if not os.path.exists(img_dir):
    os.makedirs(img_dir)

for src, dst in mapping.items():
    src_path = os.path.join(brain_dir, src)
    dst_path = os.path.join(img_dir, dst)
    try:
        print(f"Copying {src_path} to {dst_path}")
        shutil.copy2(src_path, dst_path)
    except Exception as e:
        print(f"Error copying {src}: {e}")
