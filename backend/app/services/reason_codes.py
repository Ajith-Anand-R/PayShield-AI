REASON_MAP = {
    "BOT_PATTERN_DETECTED": {
        "severity": "CRITICAL",
        "signal": "behavioral",
        "human_message": "Automated bot pattern detected based on mouse biometrics."
    },
    "BEHAVIORAL_DEVIATION": {
        "severity": "WARNING",
        "signal": "behavioral",
        "human_message": "Significant deviation from user's historical typing or mouse movement biometrics."
    },
    "COMPROMISED_DEVICE_IP": {
        "severity": "CRITICAL",
        "signal": "device",
        "human_message": "Device has been manually blacklisted or is flagged as untrusted."
    },
    "NEW_DEVICE": {
        "severity": "WARNING",
        "signal": "device",
        "human_message": "First time this transaction has been attempted from this device."
    },
    "SUSPICIOUS_IP_LOC": {
        "severity": "WARNING",
        "signal": "device",
        "human_message": "Device IP or location does not match historically registered signals."
    },
    "IMPOSSIBLE_TRAVEL": {
        "severity": "CRITICAL",
        "signal": "geolocation",
        "human_message": "Impossible travel speed detected since the last transaction location."
    },
    "SUSPICIOUS_COUNTRY_CHANGE": {
        "severity": "CRITICAL",
        "signal": "geolocation",
        "human_message": "Sudden cross-border transaction initiated from a new country."
    },
    "NEW_GEOGRAPHIC_LOCATION": {
        "severity": "INFO",
        "signal": "geolocation",
        "human_message": "Transaction initiated from a location never seen before for this user."
    },
    "SUSPICIOUS_CITY_CHANGE": {
        "severity": "WARNING",
        "signal": "geolocation",
        "human_message": "Transaction location shifted unexpectedly between different cities."
    },
    "SCAM_TEXT_DETECTED": {
        "severity": "CRITICAL",
        "signal": "scam",
        "human_message": "Gemini AI classified the transaction remark as highly likely to be a scam."
    },
    "SUSPICIOUS_REMARKS": {
        "severity": "WARNING",
        "signal": "scam",
        "human_message": "Transaction remarks contain suspicious keywords associated with social engineering."
    },
    "EXTREME_ANOMALY_VELOCITY": {
        "severity": "CRITICAL",
        "signal": "anomaly",
        "human_message": "Extreme transaction frequency/amount anomaly detected."
    },
    "VELOCITY_BURST_DETECTED": {
        "severity": "WARNING",
        "signal": "anomaly",
        "human_message": "High velocity burst: multiple transactions completed in a very short window."
    },
    "HIGH_AMOUNT": {
        "severity": "INFO",
        "signal": "anomaly",
        "human_message": "Transaction amount is unusually high compared to typical user activity."
    },
    "CIRCULAR_MONEY_FLOW": {
        "severity": "CRITICAL",
        "signal": "graph",
        "human_message": "Circular money flow detected (money routed back to source user)."
    },
    "LAYERING_PATTERN": {
        "severity": "CRITICAL",
        "signal": "graph",
        "human_message": "Layering pattern detected: multi-hop transaction chain typical of money laundering."
    },
    "BURST_TRANSFERS": {
        "severity": "WARNING",
        "signal": "graph",
        "human_message": "Spike in graph transfer rate: high frequency of transactions across linked accounts."
    },
    "HUB_ACCOUNT": {
        "severity": "CRITICAL",
        "signal": "graph",
        "human_message": "Account acts as a hub: sending transfers to multiple distinct beneficiaries."
    },
    "FUNNEL_ACCOUNT": {
        "severity": "CRITICAL",
        "signal": "graph",
        "human_message": "Account acts as a funnel: receiving transfers from multiple users typical of mule accounts."
    },
    "FRAUD_RING_LINK": {
        "severity": "CRITICAL",
        "signal": "graph",
        "human_message": "Linked directly or closely to a known fraudster or flagged account in the network."
    },
    "SHARED_COMPROMISED_DEVICE": {
        "severity": "CRITICAL",
        "signal": "graph",
        "human_message": "User is sharing a device that was previously linked to a fraudulent transaction."
    },
    "SUSPICIOUS_RISK_AGGREGATION": {
        "severity": "WARNING",
        "signal": "fusion",
        "human_message": "Aggregated risk indicators exceed safety threshold, although no single signal is critical."
    }
}

def get_reason_detail(code: str) -> dict:
    """
    Returns a dictionary with structured details for a given reason code.
    Format: {"code": str, "severity": str, "signal": str, "human_message": str}
    """
    # 1. Exact match
    if code in REASON_MAP:
        detail = REASON_MAP[code].copy()
        detail["code"] = code
        return detail
        
    # 2. Dynamic matches
    if code.startswith("NEW_BENEFICIARY_"):
        parts = code.split("_")
        hours = "24"
        if len(parts) >= 3 and parts[2].endswith("H"):
            hours = parts[2][:-1]
        return {
            "code": code,
            "severity": "WARNING",
            "signal": "anomaly",
            "human_message": f"Beneficiary account was added recently ({hours} hours ago)."
        }
        
    if "x_ABOVE_AVERAGE" in code:
        parts = code.split("_")
        multiplier = "2.0"
        if len(parts) >= 2 and parts[1].endswith("x"):
            multiplier = parts[1][:-1]
        return {
            "code": code,
            "severity": "WARNING",
            "signal": "anomaly",
            "human_message": f"Transaction amount is {multiplier}x above the user's historical average."
        }
        
    # Default fallback
    return {
        "code": code,
        "severity": "INFO",
        "signal": "fusion",
        "human_message": f"Elevated risk indicator: {code.replace('_', ' ').title()}"
    }
