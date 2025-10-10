#!/usr/bin/env python3
# Whisper: push-to-talk STT that types anywhere on Windows 11
# One-file app with a tiny settings UI, global hotkey, and OpenAI STT (gpt-4o-transcribe/whisper-1)
# Elegantly compact, reasonably commented, and dependency-light.

import os, io, json, sys, threading, time, wave, queue, ctypes, traceback
from pathlib import Path

# --- Third‑party deps (install via requirements.txt) ---
# sounddevice (mic), numpy (buffer/gain), keyboard (global hotkeys & typing), pyperclip (fast paste), openai (API)
import numpy as np
import sounddevice as sd
import keyboard, pyperclip

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None
    Image = None
    ImageDraw = None

# --- Constants & defaults ---
APP = "Whisper"
APPDIR = Path(os.getenv("APPDATA") or Path.home()/"AppData"/"Roaming")/APP
APPDIR.mkdir(parents=True, exist_ok=True)
CFG_PATH = APPDIR/"config.json"
DEFAULTS = {
    "model": "whisper-1",           # OpenAI Whisper model
    "hotkey": "ctrl+0",
    "output_mode": "paste",         # paste|type
    "gain": 1.0,                     # 0.5–3.0 recommended
    "device": None,                  # sounddevice input device index or None
    "language": None,                # e.g., "en" to force, else auto
    "api_key_strategy": "env",      # env|inline (inline stores in config file)
    "api_key": ""                   # used only if api_key_strategy=="inline"
}

# --- Small helpers ---
log = lambda *a, **k: print("[Whisper]", *a, **k)
err = lambda *a, **k: print("[Whisper:ERROR]", *a, file=sys.stderr, **k)

def load_cfg():
    if CFG_PATH.exists():
        try:
            d = json.loads(CFG_PATH.read_text("utf-8"))
            return {**DEFAULTS, **d}
        except Exception as e:
            err("Bad config; using defaults:", e)
    return DEFAULTS.copy()

CFG = load_cfg()

def save_cfg():
    try:
        CFG_PATH.write_text(json.dumps(CFG, separators=(",",":")))
    except Exception as e:
        err("Failed saving config:", e)

# Windows native clipboard sanity check (fix rare clipboard busy states)
CF_TEXT = 1
user32 = ctypes.windll.user32 if os.name == "nt" else None
kernel32 = ctypes.windll.kernel32 if os.name == "nt" else None

# --- Audio recording (push-to-talk) ---
class Recorder:
    def __init__(self, sr=16000, ch=1):
        self.sr, self.ch = sr, ch
        self.frames = []
        self.lock = threading.Lock()
        self.stream = None
        self.recording = False

    def _callback(self, indata, frames, t, status):
        if status: 
            log(f"Audio status: {status}")
        try:
            g = float(CFG.get("gain", 1.0))
            # apply software gain + int16 clip
            d = (indata.astype(np.float32) * g).clip(-32768, 32767).astype(np.int16)
            with self.lock:
                self.frames.append(d.copy())
        except Exception as e:
            err(f"Audio callback error: {e}")

    def start(self):
        if self.recording: return
        self.frames.clear()
        self.stream = sd.InputStream(samplerate=self.sr, channels=self.ch, dtype='int16', device=CFG.get("device"), callback=self._callback)
        self.stream.start(); self.recording = True
        log("REC START")

    def stop(self):
        if not self.recording: 
            return b""
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
        except Exception as e:
            err(f"Error stopping audio stream: {e}")
        finally:
            self.stream = None
            self.recording = False
            
        with self.lock:
            audio = np.concatenate(self.frames, axis=0) if self.frames else np.zeros((0,self.ch), dtype=np.int16)
            
        if len(audio) == 0:
            log("No audio data recorded")
            return b""
            
        try:
            buf = io.BytesIO()
            with wave.open(buf,'wb') as wf:
                wf.setnchannels(self.ch)
                wf.setsampwidth(2) 
                wf.setframerate(self.sr)
                wf.writeframes(audio.tobytes())
            buf.seek(0)
            wav_bytes = buf.read()
            log(f"REC STOP — {len(wav_bytes)} bytes, {len(audio)} samples, {len(audio)/self.sr:.1f}s")
            return wav_bytes
        except Exception as e:
            err(f"Error creating WAV file: {e}")
            return b""

REC = Recorder()

# --- OpenAI STT ---
class Transcriber:
    def __init__(self):
        self.client = None
        self._init_client()

    def _resolve_api_key(self):
        if CFG.get("api_key_strategy") == "inline" and CFG.get("api_key"): return CFG["api_key"]
        return os.getenv("OPENAI_API_KEY", "")

    def _init_client(self):
        key = self._resolve_api_key()
        if not key:
            err("Missing API key. Set OPENAI_API_KEY environment variable or configure it in Settings.")
            self.client = None
            return
        if OpenAI is None:
            err("openai package not available. Install with: pip install openai")
            self.client = None
            return
        try:
            self.client = OpenAI(api_key=key)
            log("OpenAI client initialized successfully")
        except Exception as e:
            err(f"Failed to initialize OpenAI client: {e}")
            self.client = None

    def transcribe(self, wav_bytes: bytes) -> str:
        if not self.client: self._init_client()
        if not self.client: raise RuntimeError("OpenAI client not initialized")
        
        # Use only whisper-1 model as it's the official OpenAI Whisper model
        model = CFG.get("model") or "whisper-1"
        lang = CFG.get("language")
        
        try:
            # Create file-like object with proper name for OpenAI API
            audio_file = io.BytesIO(wav_bytes)
            audio_file.name = "speech.wav"  # OpenAI API needs filename for format detection
            
            # Create transcription with proper parameters
            if lang:
                result = self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file,
                    language=lang
                )
            else:
                result = self.client.audio.transcriptions.create(
                    model=model,
                    file=audio_file
                )
            
            # Extract text from response
            transcribed_text = result.text.strip() if hasattr(result, 'text') else str(result).strip()
            log(f"Transcribed successfully with {model}: '{transcribed_text[:50]}{'...' if len(transcribed_text) > 50 else ''}'")
            return transcribed_text
            
        except Exception as e:
            error_msg = f"Transcription failed with {model}: {str(e)}"
            log(error_msg)
            raise RuntimeError(error_msg)

TRANS = Transcriber()

# --- Output injection (type or paste) ---
class Injector:
    @staticmethod
    def paste(text: str):
        # Fast & reliable: copy, send Ctrl+V (respects target app formatting)
        old = pyperclip.paste()
        pyperclip.copy(text)
        time.sleep(0.02)
        keyboard.send("ctrl+v")
        # Optional: restore previous clipboard (best-effort & async so we don't block typing)
        threading.Timer(0.3, lambda: pyperclip.copy(old)).start()

    @staticmethod
    def type(text: str):
        keyboard.write(text, delay=0.0)  # blazing fast; set small delay if needed

    @staticmethod
    def inject(text: str):
        (Injector.paste if CFG.get("output_mode") == "paste" else Injector.type)(text)

INJECT = Injector()

# --- Hotkey flow ---
state = {"busy": False, "recording": False, "enabled": True}

def on_hotkey():
    if not state["enabled"]:
        log("Whisper is disabled - press \\ to enable")
        return
        
    if state["busy"]:
        log("Busy processing previous recording; ignoring hotkey")
        return
    if not state["recording"]:
        try:
            REC.start()
            state["recording"] = True
            log("Recording started - press hotkey again to stop and transcribe")
        except Exception as e:
            err(f"Failed to start recording: {e}")
            state["recording"] = False
    else:
        wav = b""
        try:
            wav = REC.stop()
            state["recording"] = False
        except Exception as e:
            err(f"Failed to stop recording: {e}")
            state["recording"] = False
            return
            
        if not wav or len(wav) < 2000:  # tiny buffers = accidental taps
            log("Recording discarded (too short - speak longer next time)")
            return
            
        log(f"Processing {len(wav)} bytes of audio...")
        
        def worker():
            state["busy"] = True
            try:
                txt = TRANS.transcribe(wav)
                if txt:
                    log(f"Transcription successful: '{txt[:100]}{'...' if len(txt) > 100 else ''}'")
                    INJECT.inject(txt)
                    log("Text injected successfully")
                else:
                    log("Transcription returned empty text")
            except Exception as e:
                err(f"Transcription failed: {e}")
                # Print more detailed error for debugging
                if "API" in str(e) or "key" in str(e).lower():
                    err("Check your OpenAI API key in Settings")
                elif "network" in str(e).lower() or "connection" in str(e).lower():
                    err("Check your internet connection")
            finally:
                state["busy"] = False
                
        threading.Thread(target=worker, daemon=True).start()

def on_toggle_hotkey():
    """Toggle Whisper on/off with backslash key"""
    state["enabled"] = not state["enabled"]
    status = "ENABLED" if state["enabled"] else "DISABLED"
    log(f"Whisper {status}")
    
    # Update system tray icon
    TRAY.update_icon()
    
    # If disabling while recording, stop the recording
    if not state["enabled"] and state["recording"]:
        try:
            REC.stop()
            state["recording"] = False
            log("Recording stopped (Whisper disabled)")
        except Exception as e:
            err(f"Error stopping recording: {e}")

# --- System Tray functionality ---
class SystemTray:
    def __init__(self):
        self.icon = None
        self.settings_window = None
        
    def create_icon_image(self, enabled=True):
        """Create a simple microphone icon for the system tray"""
        if not Image or not ImageDraw:
            return None
            
        # Create a 64x64 image
        width = height = 64
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw microphone shape
        color = (0, 150, 0) if enabled else (150, 0, 0)  # Green if enabled, red if disabled
        
        # Microphone body (rectangle)
        draw.rectangle([20, 15, 44, 35], fill=color, outline=color)
        
        # Microphone grille lines  
        for y in range(18, 33, 3):
            draw.line([22, y, 42, y], fill=(255, 255, 255), width=1)
            
        # Stand (vertical line)
        draw.line([32, 35, 32, 45], fill=color, width=3)
        
        # Base (horizontal line)
        draw.line([25, 45, 39, 45], fill=color, width=3)
        
        return image
        
    def create_menu(self):
        """Create the right-click context menu"""
        status_text = "✓ Enabled" if state["enabled"] else "✗ Disabled"
        return pystray.Menu(
            pystray.MenuItem(f"Whisper STT - {status_text}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Settings", self.show_settings),
            pystray.MenuItem("Toggle Enable/Disable", self.toggle_whisper),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.quit_app)
        )
        
    def show_settings(self, icon=None, item=None):
        """Show the settings window"""
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsUI()
            # Make sure window appears on top
            self.settings_window.lift()
            self.settings_window.attributes('-topmost', True)
            self.settings_window.after_idle(self.settings_window.attributes, '-topmost', False)
        else:
            # Bring existing window to front
            self.settings_window.lift()
            self.settings_window.deiconify()
            
    def toggle_whisper(self, icon=None, item=None):
        """Toggle Whisper on/off from tray menu"""
        on_toggle_hotkey()  # Use existing toggle function
        self.update_icon()
        
    def update_icon(self):
        """Update the tray icon to reflect current status"""
        if self.icon:
            new_image = self.create_icon_image(state["enabled"])
            new_menu = self.create_menu()
            self.icon.icon = new_image
            self.icon.menu = new_menu
            
    def quit_app(self, icon=None, item=None):
        """Completely exit the application"""
        log("Exiting Whisper application...")
        if self.icon:
            self.icon.stop()
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.quit()
        os._exit(0)  # Force exit
        
    def start_tray(self):
        """Start the system tray icon"""
        if not pystray or not Image:
            err("System tray dependencies not available. Install: pip install pystray pillow")
            return False
            
        try:
            image = self.create_icon_image(state["enabled"])
            menu = self.create_menu()
            
            self.icon = pystray.Icon(
                name="WhisperSTT",
                icon=image,
                title="Whisper Speech-to-Text",
                menu=menu
            )
            
            # Run tray icon in separate thread
            threading.Thread(target=self.icon.run, daemon=True).start()
            log("System tray icon started")
            return True
            
        except Exception as e:
            err(f"Failed to start system tray: {e}")
            return False

TRAY = SystemTray()

# --- Settings UI (tkinter, compact) ---
import tkinter as tk
from tkinter import ttk, messagebox

class SettingsUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP} Settings"); self.geometry("520x450")
        self.resizable(False, False)
        
        # Handle window close button to minimize to tray instead of exit
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        p = ttk.Frame(self, padding=10); p.pack(fill="both", expand=True)
        r = 0
        def add(label, widget):
            nonlocal r
            ttk.Label(p, text=label, width=18).grid(row=r, column=0, sticky="w", pady=4)
            widget.grid(row=r, column=1, sticky="ew", pady=4)
            r += 1
        p.columnconfigure(1, weight=1)

        # API key strategy
        strat = tk.StringVar(value=CFG.get("api_key_strategy","env"))
        sbox = ttk.Combobox(p, values=["env","inline"], textvariable=strat, state="readonly")
        add("API key source", sbox)

        # API key entry
        api = tk.StringVar(value=CFG.get("api_key",""))
        aentry = ttk.Entry(p, textvariable=api, show="*")
        add("API key (inline)", aentry)

        # Model
        model = tk.StringVar(value=CFG.get("model","whisper-1"))
        mbox = ttk.Combobox(p, values=["whisper-1"], textvariable=model, state="readonly")
        add("Model", mbox)

        # Language
        lang = tk.StringVar(value=CFG.get("language") or "")
        lentry = ttk.Entry(p, textvariable=lang)
        add("Language (optional)", lentry)

        # Hotkey capture
        hk = tk.StringVar(value=CFG.get("hotkey","ctrl+alt+."))
        hkentry = ttk.Entry(p, textvariable=hk)
        def cap():
            messagebox.showinfo(APP, "Press your desired hotkey combo now… (ESC to cancel)")
            try:
                combo = keyboard.read_hotkey(suppress=False)
                if combo: hk.set(combo)
            except Exception as e:
                messagebox.showerror(APP, f"Failed recording hotkey: {e}")
        capbtn = ttk.Button(p, text="Capture…", command=cap)
        row = r; add("Hotkey (toggle)", hkentry); capbtn.grid(row=row, column=2, padx=6)

        # Output mode
        om = tk.StringVar(value=CFG.get("output_mode","paste"))
        obox = ttk.Combobox(p, values=["paste","type"], textvariable=om, state="readonly")
        add("Output mode", obox)

        # Gain
        g = tk.DoubleVar(value=float(CFG.get("gain",1.0)))
        gscale = ttk.Scale(p, from_=0.5, to=3.0, value=g.get(), command=lambda v: g.set(float(v)))
        add("Mic gain", gscale)

        # Device
        devs = sd.query_devices(); in_ids = [i for i,d in enumerate(devs) if d.get('max_input_channels',0)>0]
        labels = [f"{i}: {devs[i]['name']}" for i in in_ids]
        dev = tk.StringVar(value=("None" if CFG.get("device") is None else str(CFG.get("device"))))
        dbox = ttk.Combobox(p, values=["None"]+labels, textvariable=dev, state="readonly")
        add("Input device", dbox)

        # Buttons
        btns = ttk.Frame(p); btns.grid(row=r, column=0, columnspan=3, pady=12, sticky="e"); r+=1
        def save():
            CFG["api_key_strategy"] = strat.get()
            CFG["api_key"] = api.get() if strat.get()=="inline" else ""
            CFG["model"] = model.get()
            CFG["language"] = (lang.get().strip() or None)
            CFG["hotkey"] = hk.get().strip() or DEFAULTS["hotkey"]
            CFG["output_mode"] = om.get()
            CFG["gain"] = round(float(g.get()),2)
            dv = dev.get()
            CFG["device"] = None if (not dv or dv=="None") else int(dv.split(":",1)[0])
            save_cfg()
            
            # Rebind all hotkeys with new settings
            ensure_hotkey()
            messagebox.showinfo(APP, "Saved. Hotkeys rebound.\n\nRecording: " + CFG["hotkey"] + "\nToggle: \\")
        def test_rec():
            # Quick 3s test that records, transcribes, and shows result
            try:
                rbtn.config(state="disabled")
                rbtn.config(text="Recording...")
                self.update_idletasks()
                
                def complete_test():
                    try:
                        wav_data = REC.stop()
                        rbtn.config(text="Transcribing...")
                        self.update_idletasks()
                        
                        if not wav_data or len(wav_data) < 1000:
                            messagebox.showwarning(APP, "Recording too short or empty. Try speaking during the 3-second test.")
                            return
                            
                        # Test transcription
                        try:
                            text = TRANS.transcribe(wav_data)
                            if text:
                                messagebox.showinfo(APP, f"Test successful!\n\nTranscription: \"{text}\"")
                            else:
                                messagebox.showwarning(APP, "Test completed but no text was transcribed. Check your microphone and API key.")
                        except Exception as trans_e:
                            messagebox.showerror(APP, f"Transcription test failed: {trans_e}")
                            
                    except Exception as stop_e:
                        messagebox.showerror(APP, f"Recording stop failed: {stop_e}")
                    finally:
                        rbtn.config(state="normal", text="Test Mic (3s)")
                        
                REC.start()
                self.after(3000, complete_test)  # 3 seconds for better testing
                
            except Exception as e:
                rbtn.config(state="normal", text="Test Mic (3s)")
                messagebox.showerror(APP, f"Test failed to start: {e}")
        sbtn = ttk.Button(btns, text="Save", command=save); sbtn.pack(side="right", padx=6)
        rbtn = ttk.Button(btns, text="Test Mic (3s)", command=test_rec); rbtn.pack(side="right", padx=6)

        # Hotkey info
        ttk.Label(p, text="Toggle hotkey: \\ (enable/disable Whisper)", foreground="#333", font=("TkDefaultFont", 9, "bold")).grid(row=r, column=0, columnspan=3, pady=(6,2), sticky="w"); r+=1
        
        # Footer hint
        ttk.Label(p, text="Tip: Use Paste mode for large blocks; Type mode for apps that block paste.", foreground="#666").grid(row=r, column=0, columnspan=3, pady=6, sticky="w"); r+=1
        
        # Tray hint
        ttk.Label(p, text="💡 Closing this window minimizes to system tray. Right-click tray icon for options.", foreground="#0066CC", font=("TkDefaultFont", 8)).grid(row=r, column=0, columnspan=3, pady=(2,6), sticky="w"); r+=1

    def on_closing(self):
        """Handle window close button - minimize to tray instead of exit"""
        log("Settings window closed - app minimized to system tray")
        self.withdraw()  # Hide the window
        TRAY.settings_window = None  # Clear reference

# --- App bootstrap ---

def ensure_hotkey():
    hk = CFG.get("hotkey") or DEFAULTS["hotkey"]
    try:
        # Clear any existing hotkeys first
        keyboard.clear_all_hotkeys()
        
        # Bind main recording hotkey
        keyboard.add_hotkey(hk, on_hotkey)
        log(f"Recording hotkey bound: {hk} (tap once to start, tap again to stop & transcribe)")
        
        # Bind toggle hotkey (backslash)
        keyboard.add_hotkey("\\", on_toggle_hotkey)
        log("Toggle hotkey bound: \\ (press to enable/disable Whisper)")
        
        # Show current status
        status = "ENABLED" if state["enabled"] else "DISABLED"
        log(f"Whisper is currently {status}")
        
    except Exception as e:
        err("Failed to bind hotkeys:", e)


def main():
    # First run: write defaults
    if not CFG_PATH.exists(): save_cfg()
    ensure_hotkey()
    
    # Start system tray
    tray_started = TRAY.start_tray()
    if not tray_started:
        log("Running without system tray support")
    
    # Show settings UI initially, then keep app running in background
    ui = SettingsUI()
    TRAY.settings_window = ui
    
    try:
        ui.mainloop()  # This will run until window is closed (minimized to tray)
    except KeyboardInterrupt:
        pass
    
    # If we get here, the settings window was closed
    # Keep the app running in background with tray icon
    if tray_started:
        log("App running in system tray. Right-click tray icon for options.")
        try:
            # Keep main thread alive while tray is running
            while TRAY.icon and TRAY.icon.visible:
                time.sleep(1)
        except KeyboardInterrupt:
            log("Keyboard interrupt - shutting down")
            TRAY.quit_app()
    else:
        log("No system tray - app will exit")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        err("Fatal:", e)
        traceback.print_exc()
