"""
Simple script to create an application icon
Creates a microphone icon for WhisperApp
"""
from PIL import Image, ImageDraw, ImageFont
import os


def create_icon():
    """Create a simple microphone icon"""
    # Create image
    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Colors
    bg_color = (41, 128, 185)  # Blue
    mic_color = (255, 255, 255)  # White
    accent_color = (231, 76, 60)  # Red accent

    # Draw circle background
    margin = 20
    draw.ellipse([margin, margin, size-margin, size-margin], fill=bg_color)

    # Draw microphone body
    mic_width = 60
    mic_height = 90
    mic_x = (size - mic_width) // 2
    mic_y = (size - mic_height) // 2 - 20

    # Microphone capsule (rounded rectangle)
    draw.rounded_rectangle(
        [mic_x, mic_y, mic_x + mic_width, mic_y + mic_height],
        radius=30,
        fill=mic_color
    )

    # Microphone stand
    stand_width = 4
    stand_height = 40
    stand_x = (size - stand_width) // 2
    stand_y = mic_y + mic_height

    draw.rectangle(
        [stand_x, stand_y, stand_x + stand_width, stand_y + stand_height],
        fill=mic_color
    )

    # Microphone base
    base_width = 50
    base_height = 8
    base_x = (size - base_width) // 2
    base_y = stand_y + stand_height

    draw.rounded_rectangle(
        [base_x, base_y, base_x + base_width, base_y + base_height],
        radius=4,
        fill=mic_color
    )

    # Add small red dot on microphone to indicate recording capability
    dot_size = 12
    dot_x = size // 2 - dot_size // 2
    dot_y = mic_y + 20

    draw.ellipse(
        [dot_x, dot_y, dot_x + dot_size, dot_y + dot_size],
        fill=accent_color
    )

    # Create assets directory
    assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
    os.makedirs(assets_dir, exist_ok=True)

    # Save as PNG
    png_path = os.path.join(assets_dir, 'icon.png')
    img.save(png_path, 'PNG')
    print(f"Created PNG icon: {png_path}")

    # Save as ICO (for Windows)
    ico_path = os.path.join(assets_dir, 'icon.ico')
    # Create multiple sizes for ICO
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f"Created ICO icon: {ico_path}")


if __name__ == '__main__':
    try:
        create_icon()
        print("Icon created successfully!")
    except ImportError:
        print("Pillow is required to create icons. Install with: pip install Pillow")
    except Exception as e:
        print(f"Error creating icon: {e}")
