from rembg import remove
from PIL import Image, ImageDraw, ImageFont
import io
import os

def process_image(image_bytes):
    """Remove background from image"""
    output_bytes = remove(image_bytes)
    return output_bytes

def add_watermark(image_bytes, watermark_text="idx Empire"):
    """Add watermark to image"""
    # Open image
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    
    # Create watermark layer
    watermark = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)
    
    # Try to load font, fallback to default
    try:
        font = ImageFont.truetype("assets/font.ttf", 40)
    except:
        font = ImageFont.load_default()
    
    # Calculate text size and position (bottom right)
    text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    position = (
        image.width - text_width - 20,  # Right padding
        image.height - text_height - 20  # Bottom padding
    )
    
    # Draw text with opacity
    draw.text(position, watermark_text, font=font, fill=(255, 255, 255, 76))  # 30% opacity
    
    # Composite images
    watermarked = Image.alpha_composite(image, watermark)
    
    # Convert back to bytes
    output = io.BytesIO()
    watermarked.save(output, format='PNG')
    return output.getvalue()

def add_color_background(image_bytes, color_rgb):
    """Add solid color background"""
    # Open transparent image
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    
    # Create background
    background = Image.new("RGBA", image.size, color_rgb + (255,))
    
    # Composite
    final_image = Image.alpha_composite(background, image)
    
    # Convert back to bytes
    output = io.BytesIO()
    final_image.save(output, format='PNG')
    return output.getvalue()
