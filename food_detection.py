
from io import BytesIO
from PIL import Image, UnidentifiedImageError


DEMO_FOODS = [
    {"name": "Eggs", "quantity": 6, "unit": "items", "category": "Dairy & Eggs"},
    {"name": "Milk", "quantity": 1, "unit": "carton", "category": "Dairy"},
    {"name": "Cheddar Cheese", "quantity": 1, "unit": "pack", "category": "Dairy"},
    {"name": "Tomatoes", "quantity": 3, "unit": "items", "category": "Vegetables"},
    {"name": "Lettuce", "quantity": 1, "unit": "head", "category": "Vegetables"},
    {"name": "Butter", "quantity": 1, "unit": "pack", "category": "Dairy"},
]


def validate_image(image_bytes):
    """Validate image bytes without saving the image to disk."""
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def detect_foods(image_bytes_list):
    """
    Temporary demo implementation.
    Replace this with a real vision model later.
    """
    if not image_bytes_list:
        raise ValueError("Please provide at least one image.")

    if len(image_bytes_list) > 8:
        raise ValueError("A maximum of 8 images is allowed.")

    for image_bytes in image_bytes_list:
        if not validate_image(image_bytes):
            raise ValueError("One of the uploaded files is not a valid image.")

    # Demo only: these foods are not actually detected from the photos.
    return [item.copy() for item in DEMO_FOODS]
