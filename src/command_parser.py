"""
Command Parser for WhisperApp
Parses voice commands into structured actions
"""
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class Command:
    """Represents a parsed command"""
    action: str  # 'move_window', 'focus_window', etc.
    monitor: Optional[int] = None
    quadrant: Optional[int] = None
    raw_text: str = ""
    confidence: float = 1.0

    def __repr__(self):
        return f"Command(action={self.action}, monitor={self.monitor}, quadrant={self.quadrant})"


class CommandParser:
    """Parses voice commands into structured actions"""

    def __init__(self):
        # Number word mappings
        self.number_words = {
            'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4,
            'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
            'won': 1,  # Common misrecognition
            'to': 2,   # Common misrecognition
            'too': 2,  # Common misrecognition
            'for': 4,  # Common misrecognition
            'fore': 4, # Common misrecognition
        }

        # Quadrant word mappings
        self.quadrant_words = {
            'top left': 1,
            'top-left': 1,
            'upper left': 1,
            'top right': 2,
            'top-right': 2,
            'upper right': 2,
            'bottom left': 3,
            'bottom-left': 3,
            'lower left': 3,
            'bottom right': 4,
            'bottom-right': 4,
            'lower right': 4,
        }

        # Compile regex patterns
        self.patterns = [
            # "Monitor [number], quadrant [number]"
            re.compile(
                r'(?:monitor|screen|display)\s+([a-z]+|\d+)[\s,]+(?:quadrant|quarter|quad)\s+([a-z]+|\d+)',
                re.IGNORECASE
            ),
            # "Screen [number], [position]"
            re.compile(
                r'(?:monitor|screen|display)\s+([a-z]+|\d+)[\s,]+(.+?)(?:\s|$)',
                re.IGNORECASE
            ),
            # "Quadrant [number]" (assumes current monitor)
            re.compile(
                r'(?:quadrant|quarter|quad)\s+([a-z]+|\d+)',
                re.IGNORECASE
            ),
        ]

    def parse_number(self, text: str) -> Optional[int]:
        """
        Parse a number from text (handles both digits and words)

        Args:
            text: Text containing a number

        Returns:
            Integer or None if not parsable
        """
        text = text.strip().lower()

        # Try to parse as digit
        if text.isdigit():
            return int(text)

        # Try to parse as number word
        if text in self.number_words:
            return self.number_words[text]

        return None

    def parse_quadrant(self, text: str) -> Optional[int]:
        """
        Parse a quadrant from text

        Args:
            text: Text containing quadrant description

        Returns:
            Quadrant number (1-4) or None
        """
        text = text.strip().lower()

        # Try number parsing first
        num = self.parse_number(text)
        if num and 1 <= num <= 4:
            return num

        # Try quadrant word mapping
        for phrase, quadrant in self.quadrant_words.items():
            if phrase in text:
                return quadrant

        return None

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

        text = text.strip().lower()

        # Try each pattern
        for pattern in self.patterns:
            match = pattern.search(text)
            if match:
                groups = match.groups()

                if len(groups) == 2:
                    # Pattern with both monitor and quadrant/position
                    monitor_text, quadrant_text = groups

                    monitor = self.parse_number(monitor_text)
                    quadrant = self.parse_quadrant(quadrant_text)

                    if monitor is not None:
                        # If we have a valid monitor, create command
                        # Quadrant might be None if position wasn't recognized
                        if quadrant is not None:
                            return Command(
                                action='move_window',
                                monitor=monitor,
                                quadrant=quadrant,
                                raw_text=text
                            )
                        else:
                            # Try parsing quadrant text as number
                            quadrant = self.parse_number(quadrant_text)
                            if quadrant and 1 <= quadrant <= 4:
                                return Command(
                                    action='move_window',
                                    monitor=monitor,
                                    quadrant=quadrant,
                                    raw_text=text
                                )

                elif len(groups) == 1:
                    # Pattern with just quadrant (assumes current monitor)
                    quadrant_text = groups[0]
                    quadrant = self.parse_quadrant(quadrant_text)

                    if quadrant is not None:
                        return Command(
                            action='move_window',
                            monitor=1,  # Default to primary monitor
                            quadrant=quadrant,
                            raw_text=text
                        )

        # No pattern matched
        return None

    def is_command(self, text: str) -> bool:
        """
        Check if text is likely a command

        Args:
            text: Text to check

        Returns:
            True if text appears to be a command
        """
        if not text:
            return False

        text = text.lower()

        # Check for command keywords
        keywords = ['monitor', 'screen', 'display', 'quadrant', 'quarter', 'quad']
        return any(keyword in text for keyword in keywords)

    def get_command_examples(self) -> list:
        """Get list of example commands"""
        return [
            "monitor one, quadrant one",
            "monitor two, quadrant four",
            "screen one, top left",
            "monitor three, bottom right",
            "quadrant two",
            "screen two, upper right"
        ]

    def validate_command(self, command: Command, max_monitors: int = 9) -> tuple[bool, str]:
        """
        Validate a parsed command

        Args:
            command: Command to validate
            max_monitors: Maximum number of monitors available

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not command:
            return False, "No command provided"

        if command.monitor is None:
            return False, "Monitor number not specified"

        if command.monitor < 1 or command.monitor > max_monitors:
            return False, f"Monitor {command.monitor} is out of range (1-{max_monitors})"

        if command.quadrant is None:
            return False, "Quadrant not specified"

        if command.quadrant < 1 or command.quadrant > 4:
            return False, f"Quadrant {command.quadrant} is invalid (must be 1-4)"

        return True, ""


# Convenience function for quick parsing
def parse_command(text: str) -> Optional[Command]:
    """
    Quick function to parse a command

    Args:
        text: Voice command text

    Returns:
        Command object or None
    """
    parser = CommandParser()
    return parser.parse(text)
