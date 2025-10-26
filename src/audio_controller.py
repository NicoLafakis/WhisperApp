"""
Audio Controller for WhisperApp
Handles system audio control on Windows
"""
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume
from ctypes import cast, POINTER
from typing import Optional, List, Dict
import math


class AudioController:
    """Controls system audio settings"""

    def __init__(self):
        self.devices = AudioUtilities.GetSpeakers()
        self.interface = self.devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        self.volume = cast(self.interface, POINTER(IAudioEndpointVolume))

        # Get volume range
        self.min_volume, self.max_volume, _ = self.volume.GetVolumeRange()

    # ============= Master Volume Control =============

    def get_master_volume(self) -> int:
        """
        Get master volume level

        Returns:
            Volume level (0-100)
        """
        try:
            current_volume = self.volume.GetMasterVolumeLevel()
            # Convert from dB to percentage
            volume_percent = self._db_to_percent(current_volume)
            return int(volume_percent)
        except Exception as e:
            print(f"Error getting master volume: {e}")
            return 0

    def set_master_volume(self, percent: int) -> bool:
        """
        Set master volume level

        Args:
            percent: Volume level (0-100)

        Returns:
            True if successful
        """
        try:
            percent = max(0, min(100, percent))  # Clamp to 0-100
            db_volume = self._percent_to_db(percent)
            self.volume.SetMasterVolumeLevel(db_volume, None)
            print(f"Set master volume to {percent}%")
            return True
        except Exception as e:
            print(f"Error setting master volume: {e}")
            return False

    def increase_volume(self, step: int = 10) -> bool:
        """
        Increase master volume

        Args:
            step: Amount to increase (0-100)

        Returns:
            True if successful
        """
        current = self.get_master_volume()
        new_volume = min(100, current + step)
        return self.set_master_volume(new_volume)

    def decrease_volume(self, step: int = 10) -> bool:
        """
        Decrease master volume

        Args:
            step: Amount to decrease (0-100)

        Returns:
            True if successful
        """
        current = self.get_master_volume()
        new_volume = max(0, current - step)
        return self.set_master_volume(new_volume)

    def volume_up(self) -> bool:
        """Increase volume by 10%"""
        return self.increase_volume(10)

    def volume_down(self) -> bool:
        """Decrease volume by 10%"""
        return self.decrease_volume(10)

    # ============= Mute Control =============

    def is_muted(self) -> bool:
        """
        Check if system is muted

        Returns:
            True if muted
        """
        try:
            return bool(self.volume.GetMute())
        except Exception as e:
            print(f"Error checking mute status: {e}")
            return False

    def mute(self) -> bool:
        """
        Mute system audio

        Returns:
            True if successful
        """
        try:
            self.volume.SetMute(1, None)
            print("Muted audio")
            return True
        except Exception as e:
            print(f"Error muting: {e}")
            return False

    def unmute(self) -> bool:
        """
        Unmute system audio

        Returns:
            True if successful
        """
        try:
            self.volume.SetMute(0, None)
            print("Unmuted audio")
            return True
        except Exception as e:
            print(f"Error unmuting: {e}")
            return False

    def toggle_mute(self) -> bool:
        """
        Toggle mute status

        Returns:
            True if successful
        """
        if self.is_muted():
            return self.unmute()
        else:
            return self.mute()

    # ============= Application Volume Control =============

    def get_application_sessions(self) -> List[Dict[str, any]]:
        """
        Get all audio sessions (applications playing audio)

        Returns:
            List of session info dictionaries
        """
        sessions = []

        try:
            session_manager = AudioUtilities.GetSessionManager()
            session_enumerator = session_manager.Sessions

            for session in session_enumerator:
                process = session.Process
                if process:
                    volume_interface = session._ctl.QueryInterface(ISimpleAudioVolume)

                    sessions.append({
                        'name': process.name(),
                        'pid': process.pid,
                        'volume': int(volume_interface.GetMasterVolume() * 100),
                        'muted': bool(volume_interface.GetMute()),
                        'session': session,
                        'volume_interface': volume_interface
                    })

        except Exception as e:
            print(f"Error getting audio sessions: {e}")

        return sessions

    def set_application_volume(self, app_name: str, percent: int) -> bool:
        """
        Set volume for specific application

        Args:
            app_name: Application name (e.g., 'chrome.exe', 'spotify.exe')
            percent: Volume level (0-100)

        Returns:
            True if successful
        """
        try:
            app_name_lower = app_name.lower()
            if not app_name_lower.endswith('.exe'):
                app_name_lower += '.exe'

            percent = max(0, min(100, percent))
            sessions = self.get_application_sessions()

            found = False
            for session in sessions:
                if session['name'].lower() == app_name_lower:
                    session['volume_interface'].SetMasterVolume(percent / 100.0, None)
                    print(f"Set {app_name} volume to {percent}%")
                    found = True

            return found

        except Exception as e:
            print(f"Error setting application volume: {e}")
            return False

    def mute_application(self, app_name: str) -> bool:
        """
        Mute specific application

        Args:
            app_name: Application name

        Returns:
            True if successful
        """
        try:
            app_name_lower = app_name.lower()
            if not app_name_lower.endswith('.exe'):
                app_name_lower += '.exe'

            sessions = self.get_application_sessions()

            found = False
            for session in sessions:
                if session['name'].lower() == app_name_lower:
                    session['volume_interface'].SetMute(1, None)
                    print(f"Muted {app_name}")
                    found = True

            return found

        except Exception as e:
            print(f"Error muting application: {e}")
            return False

    def unmute_application(self, app_name: str) -> bool:
        """
        Unmute specific application

        Args:
            app_name: Application name

        Returns:
            True if successful
        """
        try:
            app_name_lower = app_name.lower()
            if not app_name_lower.endswith('.exe'):
                app_name_lower += '.exe'

            sessions = self.get_application_sessions()

            found = False
            for session in sessions:
                if session['name'].lower() == app_name_lower:
                    session['volume_interface'].SetMute(0, None)
                    print(f"Unmuted {app_name}")
                    found = True

            return found

        except Exception as e:
            print(f"Error unmuting application: {e}")
            return False

    # ============= Audio Devices =============

    def get_audio_devices(self) -> List[Dict[str, any]]:
        """
        Get list of audio output devices

        Returns:
            List of device info dictionaries
        """
        devices = []

        try:
            from pycaw.pycaw import AudioUtilities, IMMDeviceEnumerator, EDataFlow, ERole
            from comtypes import CoCreateInstance

            device_enumerator = CoCreateInstance(
                IMMDeviceEnumerator._iid_,
                IMMDeviceEnumerator,
                CLSCTX_ALL
            )

            collection = device_enumerator.EnumAudioEndpoints(EDataFlow.eRender.value, 1)
            count = collection.GetCount()

            for i in range(count):
                device = collection.Item(i)
                try:
                    # Get device friendly name
                    from pycaw.pycaw import IMMDevice
                    from ctypes import c_wchar_p, c_void_p

                    prop_store = device.OpenPropertyStore(0)
                    # This is simplified - full implementation would query PKEY_Device_FriendlyName

                    devices.append({
                        'id': i,
                        'name': f'Device {i}',  # Simplified
                        'device': device
                    })
                except:
                    pass

        except Exception as e:
            print(f"Error getting audio devices: {e}")

        return devices

    # ============= Utility Methods =============

    def _db_to_percent(self, db: float) -> float:
        """Convert dB to percentage"""
        if db <= self.min_volume:
            return 0.0

        percent = ((db - self.min_volume) / (self.max_volume - self.min_volume)) * 100
        return max(0.0, min(100.0, percent))

    def _percent_to_db(self, percent: float) -> float:
        """Convert percentage to dB"""
        if percent <= 0:
            return self.min_volume

        db = self.min_volume + (percent / 100.0) * (self.max_volume - self.min_volume)
        return max(self.min_volume, min(self.max_volume, db))

    def get_audio_status(self) -> Dict[str, any]:
        """
        Get current audio status

        Returns:
            Dictionary with audio info
        """
        return {
            'volume': self.get_master_volume(),
            'muted': self.is_muted(),
            'applications': self.get_application_sessions()
        }
