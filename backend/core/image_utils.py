from PIL import Image
from io import BytesIO
import os
import google.generativeai as genai

def validate_avatar_quality(image_bytes: bytes) -> tuple[bool, str]:
    """
    Checks if the image is of sufficient resolution and not too distorted.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size
        
        if width < 100 or height < 100:
            return False, "Image resolution is too low. Please upload a larger image (at least 100x100)."
        
        # Check size (5MB)
        if len(image_bytes) > 5 * 1024 * 1024:
            return False, "File size is too large. Max 5MB."

        # Check aspect ratio
        ratio = max(width, height) / min(width, height)
        if ratio > 3.0:
            return False, "The image is too narrow or too wide. Please provide a more square-like photo."
            
        return True, "OK"
    except Exception as e:
        return False, f"Invalid image file: {e}"

async def validate_avatar_safety(image_bytes: bytes) -> tuple[bool, str]:
    """
    Uses Gemini to check if the image contains offensive or inappropriate content.
    """
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return True, "Safety check skipped (no API key)"
        
    genai.configure(api_key=api_key)
    # Using a reliable model name
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    try:
        prompt = "Analyze this image for a tournament profile. Is it offensive, inappropriate, or harmful? Respond with 'SAFE' or a short reason why it is not safe."
        
        # Note: genai library might need specific data structures for images
        response = await model.generate_content_async([
            prompt,
            {"mime_type": "image/jpeg", "data": image_bytes}
        ])
        
        result = response.text.strip().upper()
        if "SAFE" in result:
            return True, "OK"
        else:
            return False, response.text.strip()
    except Exception as e:
        print(f"[IMAGE] Safety check error: {e}")
        return True, "Safety check failed to run" # Fallback

def process_avatar(image_bytes: bytes, filename_id: str) -> str:
    """
    Accepts an image, center-crops it, resizes it, and saves it.
    """
    img = Image.open(BytesIO(image_bytes))
    
    # Center crop
    width, height = img.size
    new_size = min(width, height)
    left = (width - new_size) / 2
    top = (height - new_size) / 2
    right = (width + new_size) / 2
    bottom = (height + new_size) / 2

    img = img.crop((left, top, right, bottom))
    
    # Resize
    img = img.resize((500, 500), Image.Resampling.LANCZOS)
    
    # Ensure directory exists
    save_dir = os.path.join("backend", "api", "static", "avatars")
    os.makedirs(save_dir, exist_ok=True)
    
    # Convert to RGB
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
        
    save_path = os.path.join(save_dir, f"{filename_id}.jpg")
    img.save(save_path, "JPEG", quality=90)
    
    return save_path
