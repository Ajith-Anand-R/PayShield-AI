from sqlalchemy.orm import Session
from ..models.models import BehaviorProfile
from ..schemas.schemas import BehaviorSignal

class BehavioralEngine:
    @staticmethod
    def calculate_risk(db: Session, user_id: str, signal: BehaviorSignal) -> float:
        """
        Compares incoming keystroke/mouse signals against the user's saved baseline behavior profile.
        Returns a behavioral risk score between 0 and 100.
        """
        # Fetch the behavior profile for the user
        profile = db.query(BehaviorProfile).filter(BehaviorProfile.user_id == user_id).first()
        
        # If no baseline profile exists, seed it with current signals and return low risk
        if not profile:
            new_profile = BehaviorProfile(
                user_id=user_id,
                keystroke_dwell_avg=signal.keystroke_dwell,
                keystroke_flight_avg=signal.keystroke_flight,
                mouse_speed_avg=signal.mouse_speed,
                mouse_jitter_avg=signal.mouse_jitter,
                scroll_velocity_avg=signal.scroll_velocity
            )
            db.add(new_profile)
            db.commit()
            return 0.0  # Safe initial baseline
        
        # If the baseline is empty/unseeded, return 0
        if profile.keystroke_dwell_avg == 0 and profile.keystroke_flight_avg == 0:
            profile.keystroke_dwell_avg = signal.keystroke_dwell
            profile.keystroke_flight_avg = signal.keystroke_flight
            profile.mouse_speed_avg = signal.mouse_speed
            profile.mouse_jitter_avg = signal.mouse_jitter
            profile.scroll_velocity_avg = signal.scroll_velocity
            db.commit()
            return 0.0

        # Calculate absolute deviations
        dev_dwell = abs(signal.keystroke_dwell - profile.keystroke_dwell_avg) / (profile.keystroke_dwell_avg + 1e-6)
        dev_flight = abs(signal.keystroke_flight - profile.keystroke_flight_avg) / (profile.keystroke_flight_avg + 1e-6)
        dev_speed = abs(signal.mouse_speed - profile.mouse_speed_avg) / (profile.mouse_speed_avg + 1e-6)
        dev_jitter = abs(signal.mouse_jitter - profile.mouse_jitter_avg) / (profile.mouse_jitter_avg + 1e-6)
        dev_scroll = abs(signal.scroll_velocity - profile.scroll_velocity_avg) / (profile.scroll_velocity_avg + 1e-6)

        # Detect extreme bot pattern: perfectly uniform typing (dwell standard deviation is zero) or zero mouse jitter
        # In automated scripts, mouse_jitter is typically exactly 0, or mouse_speed is exactly 0
        is_bot = False
        if signal.mouse_speed > 0 and signal.mouse_jitter == 0:
            is_bot = True
        
        # Calculate combined average deviation
        avg_deviation = (dev_dwell + dev_flight + dev_speed + dev_jitter + dev_scroll) / 5.0
        
        # Map average deviation to 0-100 risk score
        # deviation of 0.20 (20%) is standard user variance
        # deviation above 0.80 (80%) is highly suspicious
        if avg_deviation <= 0.15:
            score = avg_deviation * 100.0  # 0 to 15
        elif avg_deviation <= 0.60:
            score = 15.0 + (avg_deviation - 0.15) * 100.0  # 15 to 60
        else:
            score = min(60.0 + (avg_deviation - 0.60) * 100.0, 100.0)  # up to 100
            
        if is_bot:
            score = max(score, 95.0)  # Bot detected is a critical risk
            
        # Dynamically adaptive learning: slowly update user baseline profile for minor variations
        if score < 50.0:  # Only update baseline if transaction is relatively normal/safe
            alpha = 0.05  # Learning rate (5% weight to new pattern)
            profile.keystroke_dwell_avg = (1 - alpha) * profile.keystroke_dwell_avg + alpha * signal.keystroke_dwell
            profile.keystroke_flight_avg = (1 - alpha) * profile.keystroke_flight_avg + alpha * signal.keystroke_flight
            profile.mouse_speed_avg = (1 - alpha) * profile.mouse_speed_avg + alpha * signal.mouse_speed
            profile.mouse_jitter_avg = (1 - alpha) * profile.mouse_jitter_avg + alpha * signal.mouse_jitter
            profile.scroll_velocity_avg = (1 - alpha) * profile.scroll_velocity_avg + alpha * signal.scroll_velocity
            db.commit()

        return round(score, 2)
