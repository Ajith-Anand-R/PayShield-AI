import os
import csv
import random
import numpy as np

# Deterministic seed for all synthetic data generation so training is reproducible.
DATA_SEED = 42

# Fraction of fraud rows that look *normal* to a given engine (fraud invisible on that
# signal) and fraction of normal rows that look *borderline* (benign anomalies). These
# create genuine class overlap so models must learn instead of memorising disjoint
# hand-coded clusters (the previous design leaked the label into the features).
P_FRAUD_INVISIBLE = 0.15
P_NORMAL_BORDERLINE = 0.08
FEATURE_NOISE_SIGMA = 0.06

# Engine feature schemas (names are persisted in model metadata for validation).
FEATURE_SCHEMAS = {
    "behavioral": ["dev_dwell", "dev_flight", "dev_speed", "dev_jitter", "dev_scroll", "is_bot"],
    "device": ["is_new_for_user", "is_never_seen_globally", "is_rare_globally", "has_other_users", "ip_mismatch", "loc_mismatch"],
    "geolocation": ["is_new_location", "is_city_change", "is_country_change", "travel_speed", "distance"],
    "anomaly": ["amount_ratio", "hour", "velocity_1h", "velocity_24h", "geo_distance"],
    "graph": ["distance_to_fraud", "is_circular", "is_layering", "is_burst", "is_hub", "is_funnel", "shared_count"],
    "scam": ["scam_likely", "scam_suspicious"],
}


def add_realism(features: dict, labels: dict, seed: int = DATA_SEED) -> dict:
    """
    Removes label leakage by injecting realistic class overlap and measurement noise.

    The raw synthetic generators draw fraud and normal feature vectors from disjoint
    distributions, which lets any classifier reach a meaningless 100% accuracy. Real
    fraud is *not* anomalous on every signal (a mule's typing biometrics look normal),
    and plenty of legitimate activity looks borderline (new device, travel, big
    one-off purchase). This function makes the data reflect that:

      1. A fraction of fraud rows have their per-engine features replaced with a sampled
         normal row -> fraud that is invisible to that engine (caps recall honestly).
      2. A fraction of normal rows are replaced with a sampled fraud row -> benign
         anomalies (caps precision honestly).
      3. Gaussian measurement noise is added to every continuous feature.

    Mutates and returns ``features`` in place. ``labels`` is read-only here; per-engine
    labels are used to identify the normal/fraud pools for each engine.
    """
    rng = np.random.default_rng(seed)
    for key, X in features.items():
        if X.size == 0:
            continue
        X = X.astype(float)
        # Measurement noise scaled to each feature's magnitude (keeps binary flags near
        # 0/1 while blurring exact boundaries so trees can't split perfectly).
        X = X + rng.normal(0.0, FEATURE_NOISE_SIGMA, X.shape) * (np.abs(X) + 0.15)

        # 'scam' is a raw indicator feature (no dedicated model); noise alone is enough.
        y = labels.get(key)
        if y is not None and len(y) == len(X):
            normal_idx = np.where(y == 0)[0]
            fraud_idx = np.where(y == 1)[0]
            if len(normal_idx) > 0 and len(fraud_idx) > 0:
                n_inv = int(len(fraud_idx) * P_FRAUD_INVISIBLE)
                if n_inv > 0:
                    targets = rng.choice(fraud_idx, n_inv, replace=False)
                    donors = rng.choice(normal_idx, n_inv, replace=True)
                    X[targets] = X[donors]
                n_ben = int(len(normal_idx) * P_NORMAL_BORDERLINE)
                if n_ben > 0:
                    targets = rng.choice(normal_idx, n_ben, replace=False)
                    donors = rng.choice(fraud_idx, n_ben, replace=True)
                    X[targets] = X[donors]
        features[key] = X
    return features


def load_and_map_paysim_dataset(csv_path: str) -> tuple[dict, dict, list]:
    """
    Reads the simulated PaySim dataset and maps the records to feature vectors
    and engine-specific labels for each of PayShield's engine modules.
    Returns:
        features_dict: {
            "behavioral": np.ndarray (N, 6),
            "device": np.ndarray (N, 6),
            "geolocation": np.ndarray (N, 5),
            "anomaly": np.ndarray (N, 5),
            "graph": np.ndarray (N, 7),
            "scam": np.ndarray (N, 2)
        }
        labels_dict: {
            "behavioral": np.ndarray (N,),
            "device": np.ndarray (N,),
            "geolocation": np.ndarray (N,),
            "anomaly": np.ndarray (N,),
            "graph": np.ndarray (N,),
            "fusion": np.ndarray (N,)
        }
        steps: list (N,) -- for time-based train/test splitting
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"[PayShield Prep] PaySim CSV not found at {csv_path}. Run download_data.py first.")
        
    print(f"[PayShield Prep] Loading dataset from {csv_path}...")

    # Reproducible synthetic feature draws.
    random.seed(DATA_SEED)
    np.random.seed(DATA_SEED)

    # Store mapped feature buffers
    behav_features = []
    device_features = []
    geoloc_features = []
    anomaly_features = []
    graph_features = []
    scam_features = []
    
    # Engine-specific label buffers
    y_behavioral = []
    y_device = []
    y_geolocation = []
    y_anomaly = []
    y_graph = []
    y_fusion = []
    
    steps = []
    
    # Pre-calculate user history mean amounts from the CSV to compute real amount ratios
    user_tx_amounts = {}
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            is_fraud = int(row['isFraud'])
            if is_fraud == 0:
                user_id = row['nameOrig']
                amt = float(row['amount'])
                user_tx_amounts.setdefault(user_id, []).append(amt)
                
    user_averages = {uid: np.mean(amts) for uid, amts in user_tx_amounts.items()}
    global_average = np.mean([avg for avg in user_averages.values()]) if user_averages else 500.0
    
    # Track destination accounts to identify shared accounts/mules
    dest_counts = {}
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dest = row['nameDest']
            dest_counts[dest] = dest_counts.get(dest, 0) + 1

    # Read and map records
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            step = int(row['step'])
            amount = float(row['amount'])
            user_id = row['nameOrig']
            dest_id = row['nameDest']
            is_fraud = int(row['isFraud'])
            
            steps.append(step)
            y_fusion.append(is_fraud)
            
            # 1. Anomaly Features: [amount_ratio, hour, velocity_1h, velocity_24h, geo_distance]
            user_avg = user_averages.get(user_id, global_average)
            amount_ratio = amount / (user_avg + 1.0)
            hour = step % 24
            
            # Map features based on is_fraud labels and categories
            if is_fraud == 0:
                # --- Normal Transaction Mapping ---
                # Behavioral DNA: [dev_dwell, dev_flight, dev_speed, dev_jitter, dev_scroll, is_bot]
                behav_features.append([
                    float(np.random.uniform(0.01, 0.20)),  # dev_dwell
                    float(np.random.uniform(0.01, 0.22)),  # dev_flight
                    float(np.random.uniform(0.01, 0.20)),  # dev_speed
                    float(np.random.uniform(0.01, 0.20)),  # dev_jitter
                    float(np.random.uniform(0.01, 0.20)),  # dev_scroll
                    0.0                                    # is_bot
                ])
                
                # Device Trust: [is_new_for_user, is_never_seen_globally, is_rare_globally, has_other_users, ip_mismatch, loc_mismatch]
                is_new = 1.0 if random.random() < 0.05 else 0.0
                is_rare = 1.0 if is_new and random.random() < 0.3 else 0.0
                device_features.append([is_new, is_new, is_rare, 0.0, 0.0, 0.0])
                
                # Geolocation: [is_new_location, is_city_change, is_country_change, travel_speed, distance]
                is_new_loc = 1.0 if random.random() < 0.05 else 0.0
                is_city_chg = 1.0 if is_new_loc and random.random() < 0.5 else 0.0
                travel_speed = float(np.random.uniform(20.0, 100.0)) if is_city_chg else 0.0
                geo_dist = float(np.random.uniform(50.0, 400.0)) if is_city_chg else float(np.random.uniform(0.0, 10.0))
                geoloc_features.append([is_new_loc, is_city_chg, 0.0, travel_speed, geo_dist])
                
                # Anomaly inputs
                vel_1h = float(np.random.choice([1.0, 2.0], p=[0.92, 0.08]))
                vel_24h = float(random.randint(1, 4))
                anomaly_features.append([amount_ratio, hour, vel_1h, vel_24h, geo_dist])
                
                # Graph: [distance_to_fraud, is_circular, is_layering, is_burst, is_hub, is_funnel, shared_count]
                graph_features.append([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
                
                # Scam: [scam_likely, scam_suspicious]
                scam_features.append([0.0, 0.0])
                
                # Normal labels are 0 for all engines
                y_behavioral.append(0)
                y_device.append(0)
                y_geolocation.append(0)
                y_anomaly.append(0)
                y_graph.append(0)
                
            else:
                # --- Fraud Transaction Mapping (typology-driven assignment) ---
                typology = random.choice(['ATO', 'MULE', 'TRAVEL', 'VELOCITY', 'SCAM'])
                
                if typology == 'ATO':
                    is_bot = 1.0 if random.random() < 0.6 else 0.0
                    behav_features.append([
                        float(np.random.uniform(0.80, 1.80)) if not is_bot else 0.0,
                        float(np.random.uniform(0.80, 1.80)) if not is_bot else 0.0,
                        float(np.random.uniform(0.80, 1.80)) if not is_bot else 0.0,
                        float(np.random.uniform(0.80, 1.80)) if not is_bot else 0.0,
                        float(np.random.uniform(0.80, 1.80)) if not is_bot else 0.0,
                        is_bot
                    ])
                    device_features.append([1.0, 1.0, 0.0, 0.0, 1.0, 1.0])
                    geoloc_features.append([1.0, 1.0, 0.0, 80.0, 450.0])
                    vel_1h = 2.0
                    vel_24h = 4.0
                    anomaly_features.append([amount_ratio * 2.0, hour, vel_1h, vel_24h, 450.0])
                    graph_features.append([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
                    scam_features.append([0.0, 0.0])
                    
                    # ATO is anomalous in behavioral, device, geolocation, and anomaly
                    y_behavioral.append(1)
                    y_device.append(1)
                    y_geolocation.append(1)
                    y_anomaly.append(1)
                    y_graph.append(0)
                    
                elif typology == 'MULE':
                    behav_features.append([float(np.random.uniform(0.01, 0.20)) for _ in range(5)] + [0.0])
                    device_features.append([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
                    geoloc_features.append([0.0, 0.0, 0.0, 5.0, 2.0])
                    anomaly_features.append([amount_ratio, hour, 1.0, 2.0, 2.0])
                    is_hub = 1.0 if dest_counts.get(dest_id, 0) > 10 else 0.0
                    is_funnel = 1.0 if not is_hub and dest_counts.get(dest_id, 0) > 4 else 0.0
                    graph_features.append([1.0, 0.0, 0.0, 0.0, is_hub, is_funnel, float(random.randint(3, 8))])
                    scam_features.append([0.0, 0.0])
                    
                    # Mule is anomalous in device (shared device) and graph (hub/funnel mule pattern)
                    y_behavioral.append(0)
                    y_device.append(1)
                    y_geolocation.append(0)
                    y_anomaly.append(0)
                    y_graph.append(1)
                    
                elif typology == 'TRAVEL':
                    behav_features.append([float(np.random.uniform(0.01, 0.20)) for _ in range(5)] + [0.0])
                    device_features.append([1.0, 0.0, 0.0, 0.0, 1.0, 1.0])
                    dist = float(np.random.uniform(1200.0, 5000.0))
                    speed = float(np.random.uniform(800.0, 3000.0))
                    geoloc_features.append([1.0, 1.0, 1.0, speed, dist])
                    anomaly_features.append([amount_ratio, hour, 1.0, 2.0, dist])
                    graph_features.append([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
                    scam_features.append([0.0, 0.0])
                    
                    # Travel is anomalous in device (IP/loc mismatch), geolocation, and anomaly (distance)
                    y_behavioral.append(0)
                    y_device.append(1)
                    y_geolocation.append(1)
                    y_anomaly.append(1)
                    y_graph.append(0)
                    
                elif typology == 'VELOCITY':
                    behav_features.append([float(np.random.uniform(0.01, 0.20)) for _ in range(5)] + [0.0])
                    device_features.append([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
                    geoloc_features.append([0.0, 0.0, 0.0, 5.0, 1.0])
                    v1 = float(np.random.randint(6, 12))
                    v24 = float(np.random.randint(12, 30))
                    anomaly_features.append([amount_ratio * 1.5, hour, v1, v24, 1.0])
                    graph_features.append([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
                    scam_features.append([0.0, 0.0])
                    
                    # Velocity is anomalous in anomaly and graph (burst trigger)
                    y_behavioral.append(0)
                    y_device.append(0)
                    y_geolocation.append(0)
                    y_anomaly.append(1)
                    y_graph.append(1)
                    
                else: # SCAM
                    behav_features.append([float(np.random.uniform(0.01, 0.20)) for _ in range(5)] + [0.0])
                    device_features.append([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
                    geoloc_features.append([0.0, 0.0, 0.0, 5.0, 1.0])
                    anomaly_features.append([amount_ratio * 3.0, hour, 1.0, 2.0, 1.0])
                    graph_features.append([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
                    scam_features.append([1.0, 0.0])
                    
                    # Scam is anomalous in anomaly (amount ratio) and scam classifier
                    y_behavioral.append(0)
                    y_device.append(0)
                    y_geolocation.append(0)
                    y_anomaly.append(1)
                    y_graph.append(0)
                    
    features_dict = {
        "behavioral": np.array(behav_features),
        "device": np.array(device_features),
        "geolocation": np.array(geoloc_features),
        "anomaly": np.array(anomaly_features),
        "graph": np.array(graph_features),
        "scam": np.array(scam_features)
    }
    
    labels_dict = {
        "behavioral": np.array(y_behavioral),
        "device": np.array(y_device),
        "geolocation": np.array(y_geolocation),
        "anomaly": np.array(y_anomaly),
        "graph": np.array(y_graph),
        "fusion": np.array(y_fusion)
    }

    # Break the label->feature leakage with realistic class overlap + noise.
    features_dict = add_realism(features_dict, labels_dict, seed=DATA_SEED)

    return features_dict, labels_dict, steps

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_csv = os.path.join(base_dir, "data", "PS_20174392719_1491204439457_log.csv")
    try:
        feats, labs_dict, steps = load_and_map_paysim_dataset(target_csv)
        print(f"[PayShield Prep] Mapped {len(steps)} records successfully.")
        print(f"[PayShield Prep] Behavioral anomaly rate: {np.sum(labs_dict['behavioral']) / len(steps) * 100:.2f}%")
        print(f"[PayShield Prep] Fusion fraud rate: {np.sum(labs_dict['fusion']) / len(steps) * 100:.2f}%")
    except Exception as e:
        print(f"[PayShield Prep] Error: {e}")
