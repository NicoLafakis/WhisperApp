"""
Conversation Manager for JARVIS
Coordinates voice input, NLU, function execution, and voice output
Manages conversation state and context
"""
from typing import Optional, Dict, Any, Callable
from PyQt5.QtCore import QObject, pyqtSignal
from natural_language_processor import NaturalLanguageProcessor
from text_to_speech import TextToSpeechManager
from enum import Enum


class ConversationState(Enum):
    """Conversation states"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    WAITING_FOR_CLARIFICATION = "waiting_for_clarification"


class ConversationManager(QObject):
    """
    Manages conversational AI interactions
    Coordinates between voice input, understanding, execution, and output
    """

    # Signals
    state_changed = pyqtSignal(str)  # Emits new state
    response_generated = pyqtSignal(str)  # Emits response text
    function_executed = pyqtSignal(str, dict)  # Emits (function_name, result)
    error_occurred = pyqtSignal(str)  # Emits error messages

    def __init__(self, nlu_processor: NaturalLanguageProcessor,
                 tts_manager: Optional[TextToSpeechManager] = None):
        """
        Initialize conversation manager

        Args:
            nlu_processor: NaturalLanguageProcessor instance
            tts_manager: TextToSpeechManager instance (optional)
        """
        super().__init__()
        self.nlu_processor = nlu_processor
        self.tts_manager = tts_manager
        self.state = ConversationState.IDLE

        # Context tracking
        self.last_command = None
        self.last_response = None
        self.last_window_mentioned = None
        self.last_app_mentioned = None
        self.pending_clarification = None

        # Connect TTS signals if available
        if self.tts_manager:
            self.tts_manager.audio_player.playback_started.connect(self._on_playback_started)
            self.tts_manager.audio_player.playback_finished.connect(self._on_playback_finished)

    def set_state(self, state: ConversationState):
        """
        Set conversation state

        Args:
            state: New state
        """
        self.state = state
        self.state_changed.emit(state.value)

    def process_voice_command(self, text: str, speak_response: bool = True) -> str:
        """
        Process a voice command through the full pipeline

        Args:
            text: Transcribed voice command
            speak_response: Whether to speak the response (default: True)

        Returns:
            Response text
        """
        try:
            self.set_state(ConversationState.PROCESSING)
            self.last_command = text

            # Process through NLU
            response_text, function_results = self.nlu_processor.process_command(text)

            # Emit function execution results
            for result in function_results:
                self.function_executed.emit(result["function"], result["result"])

            # Store response
            self.last_response = response_text
            self.response_generated.emit(response_text)

            # Speak response if TTS available and requested
            if speak_response and self.tts_manager and self.tts_manager.is_configured():
                self.set_state(ConversationState.SPEAKING)
                self.tts_manager.speak(response_text)
            else:
                self.set_state(ConversationState.IDLE)

            return response_text

        except Exception as e:
            error_msg = f"Error processing command: {str(e)}"
            self.error_occurred.emit(error_msg)
            self.set_state(ConversationState.IDLE)
            return error_msg

    def process_question(self, text: str, speak_response: bool = True) -> str:
        """
        Process a conversational question (no function calls)

        Args:
            text: User's question
            speak_response: Whether to speak the response

        Returns:
            Response text
        """
        try:
            self.set_state(ConversationState.PROCESSING)
            self.last_command = text

            # Process question
            response_text = self.nlu_processor.process_question(text)

            # Store response
            self.last_response = response_text
            self.response_generated.emit(response_text)

            # Speak response if TTS available
            if speak_response and self.tts_manager and self.tts_manager.is_configured():
                self.set_state(ConversationState.SPEAKING)
                self.tts_manager.speak(response_text)
            else:
                self.set_state(ConversationState.IDLE)

            return response_text

        except Exception as e:
            error_msg = f"Error processing question: {str(e)}"
            self.error_occurred.emit(error_msg)
            self.set_state(ConversationState.IDLE)
            return error_msg

    def handle_follow_up(self, text: str, speak_response: bool = True) -> str:
        """
        Handle a follow-up command that relies on context

        Args:
            text: Follow-up text
            speak_response: Whether to speak the response

        Returns:
            Response text
        """
        # The NLU already handles context through conversation history
        # This method is here for explicit follow-up handling if needed
        return self.process_voice_command(text, speak_response)

    def clear_context(self):
        """Clear conversation context and history"""
        self.nlu_processor.clear_conversation_history()
        self.last_command = None
        self.last_response = None
        self.last_window_mentioned = None
        self.last_app_mentioned = None
        self.pending_clarification = None
        self.set_state(ConversationState.IDLE)

    def stop_speaking(self):
        """Stop current TTS playback"""
        if self.tts_manager:
            self.tts_manager.stop_speaking()
        self.set_state(ConversationState.IDLE)

    def is_speaking(self) -> bool:
        """Check if currently speaking"""
        if self.tts_manager:
            return self.tts_manager.is_speaking()
        return False

    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get summary of current conversation context

        Returns:
            Dictionary with context information
        """
        return {
            "state": self.state.value,
            "last_command": self.last_command,
            "last_response": self.last_response,
            "nlu_context": self.nlu_processor.get_context_info(),
            "is_speaking": self.is_speaking()
        }

    def _on_playback_started(self, text: str):
        """Handler for when TTS playback starts"""
        self.set_state(ConversationState.SPEAKING)

    def _on_playback_finished(self):
        """Handler for when TTS playback finishes"""
        self.set_state(ConversationState.IDLE)

    def update_nlu_settings(self, model: Optional[str] = None,
                           verbosity: Optional[str] = None):
        """
        Update NLU settings

        Args:
            model: GPT model to use
            verbosity: Response verbosity level
        """
        if model:
            self.nlu_processor.update_model(model)
        if verbosity:
            self.nlu_processor.update_verbosity(verbosity)

    def update_tts_settings(self, voice: Optional[str] = None,
                           model: Optional[str] = None,
                           speed: Optional[float] = None):
        """
        Update TTS settings

        Args:
            voice: Voice to use
            model: TTS model
            speed: Speaking speed
        """
        if not self.tts_manager:
            return

        if voice:
            self.tts_manager.update_voice(voice)
        if model:
            self.tts_manager.update_model(model)
        if speed is not None:
            self.tts_manager.update_speed(speed)

    def is_configured(self) -> bool:
        """Check if conversation manager is fully configured"""
        return (self.nlu_processor.is_configured() and
                (not self.tts_manager or self.tts_manager.is_configured()))
