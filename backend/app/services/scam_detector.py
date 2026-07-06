import os
import json
import requests

class ScamDetectorService:
    @staticmethod
    def analyze_remarks(remarks: str) -> dict:
        """
        Calls Gemini API to classify the transaction remark into Safe, Suspicious, or Scam Likely.
        Has robust local keyword-based heuristics if the Gemini API is unavailable or rate-limited.
        """
        if not remarks or not remarks.strip():
            return {
                "classification": "Safe",
                "explanation": "No remark provided."
            }
            
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return ScamDetectorService._local_heuristic(remarks)
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        
        prompt = f"""
You are a banking fraud prevention AI auditing transaction remarks/descriptions.
Classify the following transaction remark/purpose into one of: "Safe", "Suspicious", or "Scam Likely".
Provide a brief, human-friendly explanation of why (max 2 sentences).

Examples of scams:
- "investment profit withdrawal" -> Scam Likely
- "part time job commission" -> Scam Likely
- "KYC verification" -> Scam Likely
- "courier customs payment" -> Scam Likely

Transaction purpose/remark: "{remarks}"

Respond ONLY in valid JSON format:
{{
  "classification": "Safe" | "Suspicious" | "Scam Likely",
  "explanation": "Brief explanation"
}}
"""
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=6)
            if response.status_code == 200:
                res_json = response.json()
                text_response = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                data = json.loads(text_response)
                return {
                    "classification": data.get("classification", "Safe"),
                    "explanation": data.get("explanation", "Gemini scam analysis complete.")
                }
        except Exception as e:
            print(f"[PayShield] Gemini Scam API call failed: {e}")
            
        # Fall back to local heuristics
        return ScamDetectorService._local_heuristic(remarks)

    @staticmethod
    def _local_heuristic(remarks: str) -> dict:
        remarks_lower = remarks.lower()
        
        scam_keywords = [
            "investment profit", "job commission", "kyc verification", 
            "customs payment", "part time", "earn money", "crypto mining",
            "double money", "free money", "winner of lottery"
        ]
        suspicious_keywords = [
            "refund", "verify", "update", "customs", "tax", "lottery", 
            "gift", "prize", "loan", "support", "helpdesk", "tech"
        ]
        
        for kw in scam_keywords:
            if kw in remarks_lower:
                return {
                    "classification": "Scam Likely",
                    "explanation": f"Locally flagged: matches potential scam pattern '{kw}'."
                }
                
        for kw in suspicious_keywords:
            if kw in remarks_lower:
                return {
                    "classification": "Suspicious",
                    "explanation": f"Locally flagged: contains suspicious keyword '{kw}'."
                }
                
        return {
            "classification": "Safe",
            "explanation": "Passed local heuristic checks."
        }
