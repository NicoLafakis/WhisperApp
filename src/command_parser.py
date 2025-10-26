"""
Enhanced Command Parser for WhisperApp
Parses voice commands into structured actions for all control systems
"""
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class Command:
    """Represents a parsed command"""
    action: str  # Primary action type
    category: str = ""  # Category: window, app, audio, keyboard, mouse, file, clipboard

    # Window navigation (original)
    monitor: Optional[int] = None
    quadrant: Optional[int] = None

    # Window operations
    window_operation: Optional[str] = None  # minimize, maximize, close, etc.

    # Application operations
    app_name: Optional[str] = None
    app_url: Optional[str] = None

    # Audio operations
    volume_level: Optional[int] = None
    audio_change: Optional[int] = None

    # Keyboard/Mouse operations
    key_combo: Optional[List[str]] = None
    text_to_type: Optional[str] = None
    mouse_action: Optional[str] = None
    position: Optional[tuple] = None

    # File operations
    file_path: Optional[str] = None
    folder_name: Optional[str] = None

    # Clipboard operations
    clipboard_action: Optional[str] = None
    clipboard_index: Optional[int] = None

    # General
    raw_text: str = ""
    confidence: float = 1.0
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        return f"Command(action={self.action}, category={self.category})"


class CommandParser:
    """Parses voice commands into structured actions"""

    def __init__(self):
        # Number word mappings
        self.number_words = {
            'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
            'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'won': 1, 'to': 2, 'too': 2, 'for': 4, 'fore': 4,
            'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
            'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
            'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
            'eighty': 80, 'ninety': 90, 'hundred': 100
        }

        # Quadrant mappings
        self.quadrant_words = {
            'top left': 1, 'top-left': 1, 'upper left': 1,
            'top right': 2, 'top-right': 2, 'upper right': 2,
            'bottom left': 3, 'bottom-left': 3, 'lower left': 3,
            'bottom right': 4, 'bottom-right': 4, 'lower right': 4,
        }

        # Command patterns for each category
        self._init_patterns()

    def _init_patterns(self):
        """Initialize all regex patterns for command parsing"""

        # Window Navigation (original)
        self.window_nav_patterns = [
            re.compile(r'(?:monitor|screen|display)\s+([a-z]+|\d+)[\s,]+(?:quadrant|quarter|quad)\s+([a-z]+|\d+)', re.I),
            re.compile(r'(?:quadrant|quarter|quad)\s+([a-z]+|\d+)', re.I),
        ]

        # Window Operations
        self.window_op_patterns = [
            re.compile(r'(minimize|minimise)\s*(?:window|this)?', re.I),
            re.compile(r'(maximize|maximise)\s*(?:window|this)?', re.I),
            re.compile(r'(close|exit)\s*(?:window|this)?', re.I),
            re.compile(r'(restore)\s*(?:window|this)?', re.I),
            re.compile(r'(center|centre)\s*(?:window|this)?', re.I),
            re.compile(r'snap\s+(left|right|top|bottom)', re.I),
            re.compile(r'move\s+(?:to\s+)?next\s+monitor', re.I),
            re.compile(r'(?:set\s+)?(?:window\s+)?(?:always\s+)?on\s+top', re.I),
        ]

        # Application Operations
        self.app_patterns = [
            re.compile(r'(?:open|launch|start|run)\s+(.+)', re.I),
            re.compile(r'(?:switch\s+to|focus\s+on?)\s+(.+)', re.I),
            re.compile(r'close\s+(.+?)(?:\s+application|\s+app)?', re.I),
            re.compile(r'(?:kill|force\s+close)\s+(.+)', re.I),
        ]

        # Audio Operations
        self.audio_patterns = [
            re.compile(r'(?:set\s+)?volume\s+(?:to\s+)?(\d+)(?:\s+percent)?', re.I),
            re.compile(r'volume\s+(up|down)', re.I),
            re.compile(r'(mute|unmute)', re.I),
            re.compile(r'toggle\s+mute', re.I),
        ]

        # Keyboard Operations
        self.keyboard_patterns = [
            re.compile(r'press\s+(.+)', re.I),
            re.compile(r'type\s+(.+)', re.I),
            re.compile(r'(save|copy|paste|cut|undo|redo|select\s+all)', re.I),
            re.compile(r'(ctrl|control|alt|shift)\s*\+\s*(.+)', re.I),
        ]

        # Mouse Operations
        self.mouse_patterns = [
            re.compile(r'(click|double\s+click|right\s+click)', re.I),
            re.compile(r'scroll\s+(up|down)(?:\s+(\d+))?', re.I),
            re.compile(r'move\s+mouse\s+to\s+(\d+)[\s,]+(\d+)', re.I),
        ]

        # File/Folder Operations
        self.file_patterns = [
            re.compile(r'open\s+(desktop|documents|downloads|pictures|videos|music|home)', re.I),
            re.compile(r'open\s+folder\s+(.+)', re.I),
            re.compile(r'create\s+folder\s+(.+)', re.I),
            re.compile(r'delete\s+folder\s+(.+)', re.I),
            re.compile(r'open\s+file\s+(.+)', re.I),
        ]

        # Clipboard Operations
        self.clipboard_patterns = [
            re.compile(r'(?:copy|paste)\s+(?:from\s+)?history\s+(?:item\s+)?(\d+)', re.I),
            re.compile(r'clear\s+clipboard', re.I),
        ]

    def parse(self, text: str) -> Optional[Command]:
        """
        Parse a voice command into a structured Command object

        Args:
            text: Voice command text

        Returns:
            Command object or None if not parsable
        """
        if not text:
            return None

        text = text.strip()
        text_lower = text.lower()

        # Try each category of commands
        parsers = [
            self._parse_window_navigation,
            self._parse_window_operation,
            self._parse_application,
            self._parse_audio,
            self._parse_keyboard,
            self._parse_mouse,
            self._parse_file,
            self._parse_clipboard,
        ]

        for parser in parsers:
            cmd = parser(text, text_lower)
            if cmd:
                cmd.raw_text = text
                return cmd

        return None

    def _parse_window_navigation(self, text: str, text_lower: str) -> Optional[Command]:
        """Parse window navigation commands (monitor/quadrant)"""
        for pattern in self.window_nav_patterns:
            match = pattern.search(text_lower)
            if match:
                groups = match.groups()

                if len(groups) == 2:
                    monitor = self.parse_number(groups[0])
                    quadrant = self.parse_quadrant(groups[1])

                    if monitor and quadrant:
                        return Command(
                            action='move_window',
                            category='window',
                            monitor=monitor,
                            quadrant=quadrant
                        )
                elif len(groups) == 1:
                    quadrant = self.parse_quadrant(groups[0])
                    if quadrant:
                        return Command(
                            action='move_window',
                            category='window',
                            monitor=1,
                            quadrant=quadrant
                        )
        return None

    def _parse_window_operation(self, text: str, text_lower: str) -> Optional[Command]:
        """Parse window operation commands (minimize, maximize, etc.)"""
        for pattern in self.window_op_patterns:
            match = pattern.search(text_lower)
            if match:
                groups = match.groups()

                if 'minimize' in text_lower or 'minimise' in text_lower:
                    return Command(action='minimize_window', category='window', window_operation='minimize')
                elif 'maximize' in text_lower or 'maximise' in text_lower:
                    return Command(action='maximize_window', category='window', window_operation='maximize')
                elif 'close' in text_lower or 'exit' in text_lower:
                    return Command(action='close_window', category='window', window_operation='close')
                elif 'restore' in text_lower:
                    return Command(action='restore_window', category='window', window_operation='restore')
                elif 'center' in text_lower or 'centre' in text_lower:
                    return Command(action='center_window', category='window', window_operation='center')
                elif 'snap' in text_lower:
                    position = groups[0] if groups else 'left'
                    return Command(action='snap_window', category='window', window_operation='snap',
                                 parameters={'position': position.lower()})
                elif 'next monitor' in text_lower:
                    return Command(action='next_monitor', category='window', window_operation='next_monitor')
                elif 'on top' in text_lower:
                    return Command(action='always_on_top', category='window', window_operation='always_on_top')

        return None

    def _parse_application(self, text: str, text_lower: str) -> Optional[Command]:
        """Parse application commands (launch, switch, close)"""
        for pattern in self.app_patterns:
            match = pattern.search(text_lower)
            if match:
                app_name = match.group(1).strip()

                if text_lower.startswith(('open', 'launch', 'start', 'run')):
                    # Check if it's a URL
                    if any(x in app_name for x in ['.com', '.org', '.net', 'http']):
                        return Command(action='open_url', category='application', app_url=app_name)
                    else:
                        return Command(action='launch_app', category='application', app_name=app_name)
                elif text_lower.startswith(('switch', 'focus')):
                    return Command(action='switch_app', category='application', app_name=app_name)
                elif 'kill' in text_lower or 'force close' in text_lower:
                    return Command(action='kill_app', category='application', app_name=app_name)
                elif 'close' in text_lower:
                    return Command(action='close_app', category='application', app_name=app_name)

        return None

    def _parse_audio(self, text: str, text_lower: str) -> Optional[Command]:
        """Parse audio commands (volume, mute)"""
        for pattern in self.audio_patterns:
            match = pattern.search(text_lower)
            if match:
                groups = match.groups()

                if 'volume' in text_lower and groups and groups[0].isdigit():
                    level = int(groups[0])
                    return Command(action='set_volume', category='audio', volume_level=level)
                elif 'volume up' in text_lower:
                    return Command(action='volume_up', category='audio', audio_change=10)
                elif 'volume down' in text_lower:
                    return Command(action='volume_down', category='audio', audio_change=-10)
                elif 'toggle mute' in text_lower:
                    return Command(action='toggle_mute', category='audio')
                elif 'mute' in text_lower:
                    return Command(action='mute', category='audio')
                elif 'unmute' in text_lower:
                    return Command(action='unmute', category='audio')

        return None

    def _parse_keyboard(self, text: str, text_lower: str) -> Optional[Command]:
        """Parse keyboard commands (press, type, shortcuts)"""
        for pattern in self.keyboard_patterns:
            match = pattern.search(text_lower)
            if match:
                groups = match.groups()

                if text_lower.startswith('type'):
                    text_to_type = match.group(1).strip()
                    return Command(action='type_text', category='keyboard', text_to_type=text_to_type)
                elif text_lower.startswith('press'):
                    keys = match.group(1).strip()
                    return Command(action='press_keys', category='keyboard', key_combo=keys.split('+'))
                elif '+' in text_lower:
                    # Shortcut like "ctrl+s"
                    keys = [g.strip() for g in groups if g]
                    return Command(action='press_shortcut', category='keyboard', key_combo=keys)
                elif any(x in text_lower for x in ['save', 'copy', 'paste', 'cut', 'undo', 'redo', 'select all']):
                    action_map = {
                        'save': 'save', 'copy': 'copy', 'paste': 'paste',
                        'cut': 'cut', 'undo': 'undo', 'redo': 'redo', 'select all': 'select_all'
                    }
                    for key, action in action_map.items():
                        if key in text_lower:
                            return Command(action=action, category='keyboard')

        return None

    def _parse_mouse(self, text: str, text_lower: str) -> Optional[Command]:
        """Parse mouse commands (click, scroll, move)"""
        for pattern in self.mouse_patterns:
            match = pattern.search(text_lower)
            if match:
                groups = match.groups()

                if 'double click' in text_lower:
                    return Command(action='double_click', category='mouse', mouse_action='double_click')
                elif 'right click' in text_lower:
                    return Command(action='right_click', category='mouse', mouse_action='right_click')
                elif 'click' in text_lower:
                    return Command(action='click', category='mouse', mouse_action='click')
                elif 'scroll' in text_lower:
                    direction = groups[0] if groups else 'down'
                    amount = int(groups[1]) if len(groups) > 1 and groups[1] else 3
                    return Command(action='scroll', category='mouse', mouse_action='scroll',
                                 parameters={'direction': direction, 'amount': amount})
                elif 'move mouse' in text_lower:
                    x, y = int(groups[0]), int(groups[1])
                    return Command(action='move_mouse', category='mouse', position=(x, y))

        return None

    def _parse_file(self, text: str, text_lower: str) -> Optional[Command]:
        """Parse file/folder commands"""
        for pattern in self.file_patterns:
            match = pattern.search(text_lower)
            if match:
                groups = match.groups()
                folder_name = groups[0].strip() if groups else None

                if 'open' in text_lower:
                    if folder_name in ['desktop', 'documents', 'downloads', 'pictures', 'videos', 'music', 'home']:
                        return Command(action='open_folder', category='file', folder_name=folder_name)
                    elif 'folder' in text_lower:
                        return Command(action='open_folder', category='file', file_path=folder_name)
                    elif 'file' in text_lower:
                        return Command(action='open_file', category='file', file_path=folder_name)
                elif 'create folder' in text_lower:
                    return Command(action='create_folder', category='file', folder_name=folder_name)
                elif 'delete folder' in text_lower:
                    return Command(action='delete_folder', category='file', folder_name=folder_name)

        return None

    def _parse_clipboard(self, text: str, text_lower: str) -> Optional[Command]:
        """Parse clipboard commands"""
        for pattern in self.clipboard_patterns:
            match = pattern.search(text_lower)
            if match:
                groups = match.groups()

                if 'history' in text_lower:
                    index = int(groups[0]) if groups and groups[0].isdigit() else 0
                    if 'paste' in text_lower:
                        return Command(action='paste_from_history', category='clipboard',
                                     clipboard_action='paste_history', clipboard_index=index)
                elif 'clear clipboard' in text_lower:
                    return Command(action='clear_clipboard', category='clipboard', clipboard_action='clear')

        return None

    def parse_number(self, text: str) -> Optional[int]:
        """Parse a number from text"""
        text = text.strip().lower()
        if text.isdigit():
            return int(text)
        if text in self.number_words:
            return self.number_words[text]
        return None

    def parse_quadrant(self, text: str) -> Optional[int]:
        """Parse a quadrant from text"""
        text = text.strip().lower()
        num = self.parse_number(text)
        if num and 1 <= num <= 4:
            return num
        for phrase, quadrant in self.quadrant_words.items():
            if phrase in text:
                return quadrant
        return None

    def is_command(self, text: str) -> bool:
        """Check if text is likely a command"""
        if not text:
            return False

        text_lower = text.lower()

        # Check for command keywords
        keywords = [
            'monitor', 'screen', 'quadrant', 'minimize', 'maximize', 'close',
            'open', 'launch', 'switch', 'volume', 'mute', 'press', 'type',
            'click', 'scroll', 'folder', 'clipboard', 'snap'
        ]

        return any(keyword in text_lower for keyword in keywords)
