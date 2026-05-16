def validate_avatar_quality(image_bytes: bytes) -> tuple[bool, str]:
    """
    Checks if the image is of sufficient resolution and not too distorted.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size
        
        if width < 200 or height < 200:
            return False, "Image resolution is too low. Please upload a larger image (at least 200x200)."
        
        # Check aspect ratio
        ratio = max(width, height) / min(width, height)
        if ratio > 2.5:
            return False, "The image is too narrow or too wide. Please provide a more square-like photo."
            
        return True, "OK"
    except Exception as e:
        return False, f"Invalid image file: {e}"

async def validate_avatar_safety(image_bytes: bytes) -> tuple[bool, str]:
    """
    Uses Gemini to check if the image contains offensive or inappropriate content.
    """
    import google.generativeai as genai
    import os
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return True, "Safety check skipped (no API key)"
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    try:
        # Construct the content for Gemini
        # image_bytes can be passed as a dictionary with mime_type and data
        prompt = "Analyze this image for a tournament profile. Is it offensive, inappropriate, or harmful? Respond with 'SAFE' or a short reason why it is not safe."
        
        response = await model.generate_content_async([
            prompt,
            {"mime_type": "image/png", "data": image_bytes}
        ])
        
        result = response.text.strip().upper()
        if "SAFE" in result:
            return True, "OK"
        else:
            return False, f"Image rejected: {response.text}"
    except Exception as e:
        print(f"[IMAGE] Safety check error: {e}")
        return True, "Safety check failed to run" # Fallback to true to avoid blocking if API is down

def process_avatar(image_bytes: bytes, startgg_id: str) -> str:
    """
    Accepts an image from Discord as bytes, center-crops it to a square, 
    resizes it to 500x500 pixels, and saves it.
    Returns the saved file path.
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
    save_dir = os.path.join("backend", "assets", "avatars")
    os.makedirs(save_dir, exist_ok=True)
    
    # Convert to RGB (standard for web/bot)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
        
    save_path = os.path.join(save_dir, f"{startgg_id}.jpg")
    img.save(save_path, "JPEG", quality=90)
    
    return save_path
