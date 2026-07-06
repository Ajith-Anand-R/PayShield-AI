import os
import csv
import random
import numpy as np

def generate_realistic_paysim_sample(output_path: str, num_records: int = 25000):
    """
    Generates a highly realistic simulated PaySim dataset with 25,000 records.
    Contains the standard PaySim columns:
    step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig, nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud
    """
    print(f"[PayShield Data] Generating {num_records} realistic PaySim transactions...")
    
    # Probabilities of transaction types
    # TRANSFER and CASH_OUT are the main types involved in fraud in the real PaySim dataset
    types = ['CASH_IN', 'CASH_OUT', 'DEBIT', 'PAYMENT', 'TRANSFER']
    type_probs = [0.25, 0.35, 0.05, 0.20, 0.15]
    
    # Headers
    headers = [
        'step', 'type', 'amount', 'nameOrig', 'oldbalanceOrg', 'newbalanceOrig', 
        'nameDest', 'oldbalanceDest', 'newbalanceDest', 'isFraud', 'isFlaggedFraud'
    ]
    
    # We will generate a base pool of accounts to create realistic repetition
    num_customers = 5000
    customers = [f"C{random.randint(100000000, 999999999)}" for _ in range(num_customers)]
    merchants = [f"M{random.randint(100000000, 999999999)}" for _ in range(1000)]
    
    # Track account balances
    balances = {c: round(random.uniform(500.0, 50000.0), 2) for c in customers}
    for m in merchants:
        balances[m] = round(random.uniform(10000.0, 1000000.0), 2)
        
    records = []
    
    # 98% Normal, 2% Fraud (typical fraud dataset is heavily imbalanced but 2% is good for a sample)
    num_fraud = int(num_records * 0.02)
    num_normal = num_records - num_fraud
    
    # Distribution of steps (representing 1-744 hours, 31 days)
    # We want a realistic hourly distribution
    steps = sorted([random.randint(1, 744) for _ in range(num_records)])
    
    # Select which indices are fraud (spread them across the timeline)
    fraud_indices = set(random.sample(range(num_records), num_fraud))
    
    # Helper to pick names
    def get_origin():
        return random.choice(customers)
        
    def get_destination(tx_type, orig):
        if tx_type == 'PAYMENT':
            return random.choice(merchants)
        else:
            dest = random.choice(customers)
            while dest == orig:
                dest = random.choice(customers)
            return dest

    for i in range(num_records):
        step = steps[i]
        is_fraud = 1 if i in fraud_indices else 0
        
        if is_fraud:
            # Fraud vectors (typically TRANSFER followed by CASH_OUT)
            tx_type = random.choice(['TRANSFER', 'CASH_OUT'])
            orig = get_origin()
            dest = get_destination(tx_type, orig)
            
            # Fraudulent transactions usually clean out the account
            orig_bal = balances.get(orig, 5000.0)
            if orig_bal <= 0:
                orig_bal = round(random.uniform(5000.0, 20000.0), 2)
                balances[orig] = orig_bal
                
            amount = orig_bal
            
            # Sometimes fraud amounts are just very large
            if random.random() < 0.3:
                amount = round(random.uniform(150000.0, 500000.0), 2)
                
            old_bal_org = orig_bal
            new_bal_org = max(0.0, old_bal_org - amount)
            balances[orig] = new_bal_org
            
            old_bal_dest = balances.get(dest, 0.0)
            new_bal_dest = old_bal_dest + amount
            balances[dest] = new_bal_dest
            
            is_flagged = 1 if (tx_type == 'TRANSFER' and amount > 200000.0) else 0
            
        else:
            # Normal Transaction
            tx_type = np.random.choice(types, p=type_probs)
            orig = get_origin()
            dest = get_destination(tx_type, orig)
            
            # Normal amount distribution (mostly smaller, log-normal shape)
            amount = round(float(np.random.lognormal(mean=5.0, sigma=1.5)), 2)
            amount = min(amount, 100000.0) # Cap normal amounts
            amount = max(amount, 1.0)
            
            old_bal_org = balances.get(orig, 1000.0)
            
            # Ensure origin has enough balance for normal withdrawals/transfers
            if tx_type in ['CASH_OUT', 'TRANSFER', 'DEBIT'] and old_bal_org < amount:
                # Add funds to balance first
                old_bal_org += round(amount + random.uniform(100.0, 1000.0), 2)
                balances[orig] = old_bal_org
                
            if tx_type in ['CASH_OUT', 'TRANSFER', 'DEBIT']:
                new_bal_org = round(old_bal_org - amount, 2)
                balances[orig] = new_bal_org
                
                old_bal_dest = balances.get(dest, 0.0)
                new_bal_dest = round(old_bal_dest + amount, 2)
                balances[dest] = new_bal_dest
            elif tx_type == 'CASH_IN':
                new_bal_org = round(old_bal_org + amount, 2)
                balances[orig] = new_bal_org
                
                old_bal_dest = balances.get(dest, 0.0)
                new_bal_dest = round(max(0.0, old_bal_dest - amount), 2)
                balances[dest] = new_bal_dest
            else: # PAYMENT (from orig to merchant)
                new_bal_org = round(old_bal_org - amount, 2)
                balances[orig] = new_bal_org
                
                old_bal_dest = balances.get(dest, 0.0)
                new_bal_dest = round(old_bal_dest + amount, 2)
                balances[dest] = new_bal_dest
                
            is_flagged = 0
            
        records.append([
            step, tx_type, amount, orig, old_bal_org, new_bal_org,
            dest, old_bal_dest, new_bal_dest, is_fraud, is_flagged
        ])
        
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(records)
        
    print(f"[PayShield Data] Generated and saved dataset to {output_path}")

def main():
    # Setup paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    
    target_csv = os.path.join(data_dir, "PS_20174392719_1491204439457_log.csv")
    
    if os.path.exists(target_csv):
        print(f"[PayShield Data] PaySim CSV already exists at {target_csv}. Skipping generation.")
        return
        
    # Generate mock PaySim dataset
    generate_realistic_paysim_sample(target_csv)

if __name__ == "__main__":
    main()
