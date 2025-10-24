"""
Recording Indicator Widget
Displays a visual animation during recording and transcription
"""
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QPainter, QColor, QPen, QFont


class RecordingIndicator(QWidget):
    """
    A floating window that displays a recording/transcription indicator
    near the bottom of the screen
    """

    def __init__(self):
        super().__init__()
        self.rotation = 0
        self.status_text = "Recording..."
        self.init_ui()

        # Timer for animation
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)

    def init_ui(self):
        """Initialize the UI"""
        # Set window flags for a frameless, always-on-top, transparent window
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool |
            Qt.WindowTransparentForInput  # Allow clicking through
        )

        # Enable transparency
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Set fixed size
        self.setFixedSize(200, 80)

        # Position near bottom center of screen
        self.position_window()

    def position_window(self):
        """Position the window near the bottom center of the screen"""
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.desktop().screenGeometry()

        # Position at bottom center, 100px from bottom
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - 100

        self.move(x, y)

    def paintEvent(self, event):
        """Custom paint event for drawing the indicator"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw semi-transparent background
        painter.setBrush(QColor(30, 30, 30, 200))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

        # Draw spinning circle
        center_x = self.width() // 2
        circle_y = 25

        painter.setPen(Qt.NoPen)

        # Draw outer circle segments
        for i in range(8):
            angle = (i * 45 + self.rotation) % 360
            opacity = int(255 * (1 - i / 8.0))

            # Calculate segment position
            import math
            radius = 15
            segment_x = center_x + radius * math.cos(math.radians(angle))
            segment_y = circle_y + radius * math.sin(math.radians(angle))

            # Draw segment
            color = QColor(100, 180, 255, opacity)
            painter.setBrush(color)
            painter.drawEllipse(int(segment_x - 3), int(segment_y - 3), 6, 6)

        # Draw status text
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 10, QFont.Bold)
        painter.setFont(font)

        text_rect = QRect(0, 50, self.width(), 25)
        painter.drawText(text_rect, Qt.AlignCenter, self.status_text)

    def update_animation(self):
        """Update the animation rotation"""
        self.rotation = (self.rotation + 10) % 360
        self.update()  # Trigger repaint

    def show_recording(self):
        """Show the indicator for recording"""
        self.status_text = "Recording..."
        self.show()
        self.timer.start(50)  # Update every 50ms for smooth animation

    def show_transcribing(self):
        """Update indicator to show transcribing status"""
        self.status_text = "Transcribing..."

    def hide_indicator(self):
        """Hide the indicator"""
        self.timer.stop()
        self.hide()
