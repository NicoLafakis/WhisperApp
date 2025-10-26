"""
Runtime hook for aifc and audio modules
Ensures deprecated audio modules are properly imported at runtime
"""
import sys

# Pre-import deprecated audio modules to ensure they're available
# These modules are deprecated in Python 3.11 and removed in 3.13
# but are still required by speech_recognition
try:
    import aifc
    import audioop
    import wave
    import sndhdr
    import chunk
    import sunau
except ImportError as e:
    print(f"Warning: Failed to import audio module: {e}")
    # Continue anyway - the application might still work
