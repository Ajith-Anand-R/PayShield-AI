from sqlalchemy.orm import Session
from ..models.models import Device
from ..schemas.schemas import DeviceSignal

class DeviceTrustEngine:
    @staticmethod
    def calculate_risk(db: Session, user_id: str, signal: DeviceSignal) -> float:
        """
        Compares incoming device fingerprints against the user's registered history.
        Returns a device risk score between 0 and 100.
        """
        # Fetch all devices registered to this user
        user_devices = db.query(Device).filter(Device.user_id == user_id).all()
        
        # If this is the user's first device, register it and mark as trusted
        if not user_devices:
            new_device = Device(
                user_id=user_id,
                device_hash=signal.device_hash,
                browser=signal.browser,
                os=signal.os,
                ip_address=signal.ip_address,
                location=signal.location,
                is_trusted=True
            )
            db.add(new_device)
            db.commit()
            return 0.0  # Perfect trust for first device entry
        
        # Check if the incoming device_hash matches any registered device
        exact_match = None
        for d in user_devices:
            if d.device_hash == signal.device_hash:
                exact_match = d
                break
                
        if exact_match:
            # Device hash exists! Check if it has been marked as untrusted/compromised
            if not exact_match.is_trusted:
                return 100.0  # Blocked device
                
            # If trusted, check if there's any IP spoofing or sudden geolocation jump
            # Standard geolocation/IP mismatch on a known device
            ip_mismatch = exact_match.ip_address != signal.ip_address
            loc_mismatch = exact_match.location != signal.location
            
            if ip_mismatch and loc_mismatch:
                # Same device, but completely different IP and location (e.g., VPN or Session Hijacking)
                return 40.0
            elif ip_mismatch:
                # Same device, different IP but same location (e.g., dynamic DHCP IP change)
                return 10.0
            return 0.0  # Perfect match
            
        # If it's a completely new device_hash for this user, calculate threat level
        # We check browser/OS and location similarities with existing devices
        loc_matches = any(d.location == signal.location for d in user_devices)
        os_matches = any(d.os == signal.os for d in user_devices)
        browser_matches = any(d.browser == signal.browser for d in user_devices)
        
        score = 50.0  # Base score for a completely new device
        
        if not loc_matches:
            score += 20.0  # Geolocation change + new device is very suspicious
        if not os_matches:
            score += 15.0  # Different operating system (e.g., user is usually on iOS, suddenly transacting from Windows)
        if not browser_matches:
            score += 10.0  # Different browser
            
        score = min(score, 95.0)  # Max out new device risk at 95 unless explicitly blacklisted
        
        # Automatically register this new device (defaults to trusted, but scoring engine flags it for this check)
        new_device = Device(
            user_id=user_id,
            device_hash=signal.device_hash,
            browser=signal.browser,
            os=signal.os,
            ip_address=signal.ip_address,
            location=signal.location,
            is_trusted=True
        )
        db.add(new_device)
        db.commit()
        
        return round(score, 2)
