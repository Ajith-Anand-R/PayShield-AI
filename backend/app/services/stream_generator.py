import asyncio
import random
import time
from datetime import datetime, timedelta
from ..schemas.schemas import TransactionScoreRequest, DeviceSignal, BehaviorSignal
from ..schemas.stream_schemas import StreamStatusResponse

# Pool of realistic user profiles (10 total)
USER_PROFILES = [
    {
        "user_id": "user_alice", "username": "alice_chennai",
        "locations": ["Chennai, IN", "Bangalore, IN"],
        "devices": [{"hash": "device_alice_macbook", "browser": "Chrome", "os": "macOS"}],
        "ips": ["192.168.1.50", "192.168.1.51", "10.0.0.5"],
        "behavior": {"dwell": 0.10, "flight": 0.15, "speed": 250.0, "jitter": 12.0, "scroll": 80.0},
        "avg_amount": 8000, "max_amount": 25000,
        "usual_accounts": ["acc_vendor_0", "acc_vendor_1", "acc_vendor_2", "acc_grocery_store"]
    },
    {
        "user_id": "user_bob", "username": "bob_mumbai",
        "locations": ["Mumbai, IN", "Pune, IN"],
        "devices": [{"hash": "device_bob_windows", "browser": "Firefox", "os": "Windows"}],
        "ips": ["192.168.1.75", "192.168.1.76"],
        "behavior": {"dwell": 0.12, "flight": 0.18, "speed": 200.0, "jitter": 10.0, "scroll": 70.0},
        "avg_amount": 12000, "max_amount": 40000,
        "usual_accounts": ["acc_bob_rent", "acc_bob_utility", "acc_bob_shopping"]
    },
    {
        "user_id": "user_charlie", "username": "charlie_delhi",
        "locations": ["Delhi, IN", "Noida, IN", "Gurgaon, IN"],
        "devices": [{"hash": "device_charlie_android", "browser": "Chrome", "os": "Android"}],
        "ips": ["192.168.2.10", "192.168.2.11", "10.0.1.5"],
        "behavior": {"dwell": 0.09, "flight": 0.13, "speed": 280.0, "jitter": 15.0, "scroll": 90.0},
        "avg_amount": 15000, "max_amount": 50000,
        "usual_accounts": ["acc_charlie_rent", "acc_charlie_electric", "acc_charlie_grocery", "acc_charlie_fuel"]
    },
    {
        "user_id": "user_diana", "username": "diana_hyderabad",
        "locations": ["Hyderabad, IN", "Secunderabad, IN"],
        "devices": [{"hash": "device_diana_iphone", "browser": "Safari", "os": "iOS"}],
        "ips": ["192.168.3.20", "192.168.3.21"],
        "behavior": {"dwell": 0.11, "flight": 0.16, "speed": 220.0, "jitter": 9.0, "scroll": 65.0},
        "avg_amount": 6000, "max_amount": 20000,
        "usual_accounts": ["acc_diana_shopping", "acc_diana_food", "acc_diana_subscription"]
    },
    {
        "user_id": "user_eve", "username": "eve_kolkata",
        "locations": ["Kolkata, IN", "Howrah, IN"],
        "devices": [{"hash": "device_eve_windows", "browser": "Edge", "os": "Windows"}],
        "ips": ["192.168.4.30", "192.168.4.31", "10.0.2.15"],
        "behavior": {"dwell": 0.13, "flight": 0.20, "speed": 190.0, "jitter": 11.0, "scroll": 75.0},
        "avg_amount": 20000, "max_amount": 60000,
        "usual_accounts": ["acc_eve_business", "acc_eve_vendor_a", "acc_eve_vendor_b", "acc_eve_utility"]
    },
    {
        "user_id": "user_frank", "username": "frank_ahmedabad",
        "locations": ["Ahmedabad, IN", "Gandhinagar, IN"],
        "devices": [{"hash": "device_frank_mac", "browser": "Firefox", "os": "macOS"}],
        "ips": ["192.168.5.40", "192.168.5.41"],
        "behavior": {"dwell": 0.10, "flight": 0.14, "speed": 260.0, "jitter": 13.0, "scroll": 85.0},
        "avg_amount": 10000, "max_amount": 35000,
        "usual_accounts": ["acc_frank_rent", "acc_frank_insurance", "acc_frank_mutual_fund"]
    },
    {
        "user_id": "user_grace", "username": "grace_jaipur",
        "locations": ["Jaipur, IN", "Ajmer, IN"],
        "devices": [{"hash": "device_grace_android", "browser": "Chrome", "os": "Android"}],
        "ips": ["192.168.6.50", "192.168.6.51"],
        "behavior": {"dwell": 0.08, "flight": 0.12, "speed": 300.0, "jitter": 14.0, "scroll": 95.0},
        "avg_amount": 4000, "max_amount": 15000,
        "usual_accounts": ["acc_grace_mobile", "acc_grace_grocery", "acc_grace_emi"]
    },
    {
        "user_id": "user_henry", "username": "henry_lucknow",
        "locations": ["Lucknow, IN", "Kanpur, IN"],
        "devices": [{"hash": "device_henry_windows", "browser": "Chrome", "os": "Windows"}],
        "ips": ["192.168.7.60", "192.168.7.61", "10.0.3.25"],
        "behavior": {"dwell": 0.14, "flight": 0.22, "speed": 170.0, "jitter": 8.0, "scroll": 60.0},
        "avg_amount": 30000, "max_amount": 100000,
        "usual_accounts": ["acc_henry_business_a", "acc_henry_business_b", "acc_henry_salary", "acc_henry_investment"]
    },
    {
        "user_id": "user_iris", "username": "iris_kochi",
        "locations": ["Kochi, IN", "Trivandrum, IN", "Calicut, IN"],
        "devices": [{"hash": "device_iris_mac", "browser": "Safari", "os": "macOS"}],
        "ips": ["192.168.8.70", "192.168.8.71"],
        "behavior": {"dwell": 0.10, "flight": 0.15, "speed": 240.0, "jitter": 11.0, "scroll": 78.0},
        "avg_amount": 7500, "max_amount": 25000,
        "usual_accounts": ["acc_iris_rent", "acc_iris_food", "acc_iris_travel"]
    },
    {
        "user_id": "user_jake", "username": "jake_chandigarh",
        "locations": ["Chandigarh, IN", "Mohali, IN", "Panchkula, IN"],
        "devices": [{"hash": "device_jake_linux", "browser": "Firefox", "os": "Linux"}],
        "ips": ["192.168.9.80", "192.168.9.81", "10.0.4.35"],
        "behavior": {"dwell": 0.11, "flight": 0.17, "speed": 210.0, "jitter": 10.0, "scroll": 72.0},
        "avg_amount": 18000, "max_amount": 55000,
        "usual_accounts": ["acc_jake_freelance", "acc_jake_hosting", "acc_jake_equipment", "acc_jake_utility"]
    },
]

# Fraud patterns to inject
FRAUD_PATTERNS = [
    "ato",                # Account takeover: wrong device + wrong location + bot behavior
    "mule_transfer",      # Large amount to unknown account from known user
    "velocity_burst",     # Many transactions in rapid succession
    "new_device_overseas",  # Transaction from completely new device + foreign location
    "fraud_ring",         # Transaction using compromised device to known mule account
]


class TransactionStreamGenerator:
    def __init__(self):
        self.running = False
        self.speed = 3.0  # seconds between transactions
        self.fraud_rate = 0.08  # 8% fraud injection
        self.total_generated = 0
        self.total_fraud_injected = 0
        self.total_blocked = 0
        self.total_allowed = 0
        self._task = None
        self._start_time = None

    def _generate_normal_transaction(self) -> TransactionScoreRequest:
        """Generate a realistic normal transaction from a random user profile."""
        profile = random.choice(USER_PROFILES)
        # Add natural jitter to behavior (±15% variance)
        jitter = lambda base: base * random.uniform(0.85, 1.15)
        # Random amount following a gaussian distribution around the user's average
        amount = max(500, random.gauss(profile["avg_amount"], profile["avg_amount"] * 0.3))
        amount = min(amount, profile["max_amount"])
        device = random.choice(profile["devices"])
        location = random.choice(profile["locations"])
        ip = random.choice(profile["ips"])
        target = random.choice(profile["usual_accounts"])
        beh = profile["behavior"]

        return TransactionScoreRequest(
            user_id=profile["user_id"],
            amount=round(amount, 2),
            currency="INR",
            channel=random.choice(["UPI", "UPI", "UPI", "NEFT", "IMPS"]),  # weighted toward UPI
            target_account=target,
            beneficiary_name=f"Vendor {target[-1].upper()}",
            beneficiary_added_at=(datetime.now() - timedelta(days=random.randint(30, 365))),
            device=DeviceSignal(
                device_hash=device["hash"],
                browser=device["browser"],
                os=device["os"],
                ip_address=ip,
                location=location
            ),
            behavior=BehaviorSignal(
                keystroke_dwell=round(jitter(beh["dwell"]), 4),
                keystroke_flight=round(jitter(beh["flight"]), 4),
                mouse_speed=round(jitter(beh["speed"]), 2),
                mouse_jitter=round(jitter(beh["jitter"]), 2),
                scroll_velocity=round(jitter(beh["scroll"]), 2)
            )
        )

    def _generate_fraud_transaction(self) -> TransactionScoreRequest:
        """Generate a fraudulent transaction pattern."""
        pattern = random.choice(FRAUD_PATTERNS)
        profile = random.choice(USER_PROFILES)

        if pattern == "ato":
            # Account takeover: foreign device, foreign location, bot-like behavior
            return TransactionScoreRequest(
                user_id=profile["user_id"],
                amount=round(random.uniform(50000, 200000), 2),
                currency="INR",
                channel="IMPS",
                target_account=f"acc_suspicious_{random.randint(100,999)}",
                beneficiary_name="Unknown Recipient",
                beneficiary_added_at=datetime.now() - timedelta(minutes=random.randint(1, 10)),
                device=DeviceSignal(
                    device_hash=f"device_attacker_{random.randint(1,99)}",
                    browser="Firefox", os="Windows",
                    ip_address=f"41.203.{random.randint(0,255)}.{random.randint(1,254)}",
                    location=random.choice(["Lagos, NG", "Unknown", "Proxy, XX"])
                ),
                behavior=BehaviorSignal(
                    keystroke_dwell=0.01, keystroke_flight=0.01,
                    mouse_speed=0.0, mouse_jitter=0.0, scroll_velocity=0.0
                )
            )
        elif pattern == "mule_transfer":
            return TransactionScoreRequest(
                user_id=profile["user_id"],
                amount=round(random.uniform(80000, 180000), 2),
                currency="INR", channel="NEFT",
                target_account="acc_mule_account_1",
                beneficiary_name="Mule Outlet",
                beneficiary_added_at=datetime.now() - timedelta(hours=random.randint(1, 4)),
                device=DeviceSignal(
                    device_hash="device_compromised_root",
                    browser="Opera", os="Linux",
                    ip_address=f"203.0.113.{random.randint(1,254)}",
                    location="Unknown"
                ),
                behavior=BehaviorSignal(
                    keystroke_dwell=0.08, keystroke_flight=0.12,
                    mouse_speed=180.0, mouse_jitter=8.0, scroll_velocity=60.0
                )
            )
        elif pattern == "velocity_burst":
            # Normal device but unusually high amount
            device = random.choice(profile["devices"])
            beh = profile["behavior"]
            return TransactionScoreRequest(
                user_id=profile["user_id"],
                amount=round(random.uniform(profile["max_amount"] * 2, profile["max_amount"] * 5), 2),
                currency="INR", channel="UPI",
                target_account=f"acc_burst_{random.randint(1,50)}",
                beneficiary_name="Rapid Transfer",
                beneficiary_added_at=datetime.now() - timedelta(minutes=15),
                device=DeviceSignal(
                    device_hash=device["hash"], browser=device["browser"], os=device["os"],
                    ip_address=random.choice(profile["ips"]),
                    location=random.choice(profile["locations"])
                ),
                behavior=BehaviorSignal(
                    keystroke_dwell=round(beh["dwell"] * 0.7, 4),
                    keystroke_flight=round(beh["flight"] * 0.6, 4),
                    mouse_speed=round(beh["speed"] * 1.5, 2),
                    mouse_jitter=round(beh["jitter"] * 0.5, 2),
                    scroll_velocity=round(beh["scroll"] * 1.8, 2)
                )
            )
        elif pattern == "new_device_overseas":
            beh = profile["behavior"]
            return TransactionScoreRequest(
                user_id=profile["user_id"],
                amount=round(random.uniform(15000, 60000), 2),
                currency="INR", channel="IMPS",
                target_account=f"acc_overseas_{random.randint(1,20)}",
                beneficiary_name="Foreign Payee",
                beneficiary_added_at=datetime.now() - timedelta(hours=2),
                device=DeviceSignal(
                    device_hash=f"device_new_{random.randint(100,999)}",
                    browser="Safari", os="iOS",
                    ip_address=f"89.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
                    location=random.choice(["London, UK", "Dubai, AE", "Singapore, SG"])
                ),
                behavior=BehaviorSignal(
                    keystroke_dwell=round(beh["dwell"] * random.uniform(0.6, 0.9), 4),
                    keystroke_flight=round(beh["flight"] * random.uniform(0.7, 1.3), 4),
                    mouse_speed=round(beh["speed"] * random.uniform(0.5, 0.8), 2),
                    mouse_jitter=round(beh["jitter"] * random.uniform(0.3, 0.7), 2),
                    scroll_velocity=round(beh["scroll"] * random.uniform(0.6, 1.0), 2)
                )
            )
        else:  # fraud_ring
            return TransactionScoreRequest(
                user_id="user_ring_member",
                amount=round(random.uniform(20000, 50000), 2),
                currency="INR", channel="NEFT",
                target_account="acc_mule_account_1",
                beneficiary_name="Mule Outlet",
                beneficiary_added_at=datetime.now() - timedelta(hours=random.randint(1, 5)),
                device=DeviceSignal(
                    device_hash="device_compromised_root",
                    browser="Chrome", os="Android",
                    ip_address=f"203.0.113.{random.randint(1,254)}",
                    location="Unknown"
                ),
                behavior=BehaviorSignal(
                    keystroke_dwell=0.07, keystroke_flight=0.10,
                    mouse_speed=150.0, mouse_jitter=5.0, scroll_velocity=55.0
                )
            )

    async def _run_loop(self, score_fn):
        """Main generation loop. score_fn is an async callable that processes a TransactionScoreRequest."""
        self._start_time = time.time()
        while self.running:
            try:
                is_fraud = random.random() < self.fraud_rate
                if is_fraud:
                    tx_req = self._generate_fraud_transaction()
                    self.total_fraud_injected += 1
                else:
                    tx_req = self._generate_normal_transaction()

                result = await score_fn(tx_req)
                self.total_generated += 1

                if result and hasattr(result, 'decision'):
                    if result.decision == "BLOCK":
                        self.total_blocked += 1
                    elif result.decision == "ALLOW":
                        self.total_allowed += 1

                # Add some jitter to the interval (±30%)
                jittered_speed = self.speed * random.uniform(0.7, 1.3)
                await asyncio.sleep(max(0.5, jittered_speed))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[PayShield Stream] Error generating transaction: {e}")
                await asyncio.sleep(2)

    def start(self, score_fn):
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._run_loop(score_fn))
        print("[PayShield Stream] Transaction stream STARTED")

    def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            self._task = None
        print("[PayShield Stream] Transaction stream STOPPED")

    def get_status(self) -> StreamStatusResponse:
        uptime = time.time() - self._start_time if self._start_time else 0
        return StreamStatusResponse(
            running=self.running,
            speed=self.speed,
            fraud_rate=self.fraud_rate,
            total_generated=self.total_generated,
            total_fraud_injected=self.total_fraud_injected,
            total_blocked=self.total_blocked,
            total_allowed=self.total_allowed,
            uptime_seconds=round(uptime, 1)
        )


# Singleton instance
stream_generator = TransactionStreamGenerator()
