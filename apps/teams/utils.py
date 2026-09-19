import os
import io
from PIL import Image
from django.core.files.base import ContentFile

def remove_player_background(image_field):
    """
    Utility to remove background from an ImageField using rembg.
    Returns a ContentFile ready to be saved.
    """
    try:
        from rembg import remove
    except ImportError:
        print("rembg not installed. Skipping background removal.")
        return None

    try:
        # Ensure we are at the start of the file
        image_field.seek(0)
        input_data = image_field.read()
        
        if not input_data:
            print("No data read from image field.")
            return None

        # Process with rembg
        output_data = remove(input_data)
        
        # Open with PIL to ensure it's a valid PNG
        img = Image.open(io.BytesIO(output_data)).convert("RGBA")
        
        # Save to a buffer
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        
        # Return as Django ContentFile
        return ContentFile(buffer.getvalue())
    except Exception as e:
        print(f"Error during background removal: {e}")
        return None

def process_trophy_background(image_path):
    """
    One-off utility to process a specific file path (like the trophy).
    """
    try:
        from rembg import remove
    except ImportError:
        return
        
    if not os.path.exists(image_path):
        return

    with open(image_path, 'rb') as f:
        input_data = f.read()
    
    output_data = remove(input_data)
    
    img = Image.open(io.BytesIO(output_data)).convert("RGBA")
    img.save(image_path.replace('.jpg', '.png').replace('.jpeg', '.png'), format="PNG")
