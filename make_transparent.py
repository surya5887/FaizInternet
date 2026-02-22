from PIL import Image
import os

img_path = r"c:\Users\Sahil Chaudhary\Desktop\Vs Code\FaizInternet\static\img\faiz_logo.jpg"
out_path = r"c:\Users\Sahil Chaudhary\Desktop\Vs Code\FaizInternet\static\img\faiz_logo.png"

if os.path.exists(img_path):
    img = Image.open(img_path).convert("RGBA")
    datas = img.getdata()

    newData = []
    # Threshold for "darkness" to be made transparent
    # The logo has purple/white which are light, background is black.
    threshold = 50
    
    for item in datas:
        # If the pixel is very dark (close to black), make it transparent
        if item[0] < threshold and item[1] < threshold and item[2] < threshold:
            newData.append((255, 255, 255, 0)) # Fully transparent
        else:
            newData.append(item)

    img.putdata(newData)
    img.save(out_path, "PNG")
    print(f"Success: Saved transparent logo to {out_path}")
else:
    print(f"Error: {img_path} not found")
