import networkx as nx
import os
import pickle
import numpy as np
from sqlalchemy.orm import Session
from ..models.models import GraphEdge, User, Device, Transaction

class FraudGraphEngine:
    _graph = nx.DiGraph()
    GRAPH_CACHE_PATH = "payshield_graph.pkl"
    _model = None

    @classmethod
    def _load_model(cls):
        if cls._model is None:
            from .training import GRAPH_MODEL_FILE
            if os.path.exists(GRAPH_MODEL_FILE):
                try:
                    with open(GRAPH_MODEL_FILE, "rb") as f:
                        cls._model = pickle.load(f)
                except Exception as e:
                    print(f"[PayShield] Error loading graph model: {e}")


    @classmethod
    def save_graph(cls):
        with open(cls.GRAPH_CACHE_PATH, "wb") as f:
            pickle.dump(cls._graph, f)

    @classmethod
    def load_graph(cls):
        if os.path.exists(cls.GRAPH_CACHE_PATH):
            with open(cls.GRAPH_CACHE_PATH, "rb") as f:
                cls._graph = pickle.load(f)
    
    @classmethod
    def sync_graph_from_db(cls, db: Session):
        """
        Loads all entities and edges from SQLite into the NetworkX graph.
        """
        cls._graph.clear()
        
        # 1. Fetch and add all users as nodes
        users = db.query(User).all()
        user_ids = {u.id for u in users}
        for u in users:
            cls._graph.add_node(
                f"user_{u.id}", 
                type="USER", 
                label=u.username, 
                is_fraudster=u.is_fraudster,
                is_compromised=False
            )
            
        # 2. Fetch and add all device connections
        devices = db.query(Device).all()
        for d in devices:
            device_node = f"device_{d.device_hash}"
            cls._graph.add_node(device_node, type="DEVICE", label=f"Device ({d.os})", is_compromised=not d.is_trusted)
            cls._graph.add_edge(f"user_{d.user_id}", device_node, type="USER_DEVICE", weight=1.0)
            
        # 3. Fetch and add all transaction target account connections
        transactions = db.query(Transaction).all()
        for tx in transactions:
            if tx.target_account in user_ids:
                target_node = f"user_{tx.target_account}"
                cls._graph.add_edge(f"user_{tx.user_id}", target_node, type="USER_TRANSFER", weight=1.0)
            else:
                account_node = f"account_{tx.target_account}"
                # Add target account node
                cls._graph.add_node(account_node, type="ACCOUNT", label=f"Acc {tx.target_account[-4:] if len(tx.target_account) > 4 else tx.target_account}", is_compromised=False)
                # Add link from user to target account
                cls._graph.add_edge(f"user_{tx.user_id}", account_node, type="USER_TRANSACTION", weight=1.0)
            
        # 4. Fetch and add explicit GraphEdge records (e.g. manual links, historical fraud rings)
        edges = db.query(GraphEdge).all()
        for e in edges:
            cls._graph.add_edge(e.source, e.target, type=e.edge_type, weight=e.weight)
        
        cls.save_graph()

    @classmethod
    def _get_transfer_graph(cls) -> nx.DiGraph:
        """Helper to get only money flow edges from the graph."""
        transfer_graph = nx.DiGraph()
        for u, v, data in cls._graph.edges(data=True):
            if data.get("type") in ("USER_TRANSFER", "USER_TRANSACTION"):
                transfer_graph.add_edge(u, v)
        return transfer_graph

    @classmethod
    def detect_circular_flow(cls, user_id: str) -> bool:
        """Detect circular money flows (e.g. A -> B -> C -> A) involving the user."""
        user_node = f"user_{user_id}"
        tg = cls._get_transfer_graph()
        if not tg.has_node(user_node):
            return False
        for succ in tg.successors(user_node):
            if nx.has_path(tg, succ, user_node):
                return True
        return False

    @classmethod
    def detect_layering(cls, user_id: str) -> bool:
        """Detect layered transfers of length >= 3 passing through the user."""
        user_node = f"user_{user_id}"
        tg = cls._get_transfer_graph()
        if not tg.has_node(user_node):
            return False
        for p in tg.predecessors(user_node):
            for s in tg.successors(user_node):
                # We have p -> user_node -> s (length 2)
                # Check if p has predecessors or s has successors to get length >= 3
                if any(p_prev != user_node for p_prev in tg.predecessors(p)):
                    return True
                if any(s_next != user_node for s_next in tg.successors(s)):
                    return True
        return False

    @classmethod
    def detect_burst_transfers(cls, db: Session, user_id: str) -> bool:
        """Detect a sudden spike in transfer frequency: >= 5 transfers in 1 hour."""
        from datetime import datetime, timedelta, timezone
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        one_hour_ago = now_utc - timedelta(hours=1)
        count = db.query(Transaction).filter(
            Transaction.user_id == user_id,
            Transaction.timestamp >= one_hour_ago
        ).count()
        return count >= 5

    @classmethod
    def detect_hub_account(cls, user_id: str) -> bool:
        """Detect hub accounts having high out-degree (sends to > 5 beneficiaries)."""
        user_node = f"user_{user_id}"
        if not cls._graph.has_node(user_node):
            return False
        out_deg = cls._graph.out_degree(user_node)
        return out_deg > 5

    @classmethod
    def detect_funnel_account(cls, user_id: str) -> bool:
        """Detect funnel accounts having high in-degree (>3) but low out-degree (<= 1)."""
        user_node = f"user_{user_id}"
        if not cls._graph.has_node(user_node):
            return False
        in_deg = cls._graph.in_degree(user_node)
        out_deg = cls._graph.out_degree(user_node)
        return in_deg > 3 and out_deg <= 1

    @classmethod
    def detect_mule_pattern(cls, user_id: str) -> bool:
        """High in-degree (many senders) + low out-degree (one or two receivers) = mule"""
        return cls.detect_funnel_account(user_id)

    @classmethod
    def get_shared_device_users(cls, user_id: str) -> list:
        """Find all other users sharing a device with this user"""
        node = f"user_{user_id}"
        shared = set()
        if not cls._graph.has_node(node):
            return []
        neighbors = set(cls._graph.predecessors(node)) | set(cls._graph.successors(node))
        for neighbor in neighbors:
            if cls._graph.nodes.get(neighbor, {}).get("type") == "DEVICE":
                device_neighbors = set(cls._graph.predecessors(neighbor)) | set(cls._graph.successors(neighbor))
                for other in device_neighbors:
                    if other != node and cls._graph.nodes.get(other, {}).get("type") == "USER":
                        shared.add(other.replace("user_", ""))
        return list(shared)

    @classmethod
    def calculate_risk(cls, db: Session, user_id: str, device_hash: str, target_account: str) -> tuple[float, dict]:
        """
        Evaluates relationships between user, device, and target account.
        Checks closeness to known fraud nodes or clusters, plus structural mule patterns.
        Returns a tuple of (graph_risk_score, graph_signals_dict).
        """
        user_node = f"user_{user_id}"
        device_node = f"device_{device_hash}"
        account_node = f"account_{target_account}"
        target_node = account_node
        target_is_user = db.query(User).filter(User.id == target_account).first() is not None
        if target_is_user:
            target_node = f"user_{target_account}"
        
        # Ensure current nodes exist in the NetworkX graph for pathfinding
        if not cls._graph.has_node(user_node):
            cls._graph.add_node(user_node, type="USER", label=user_id, is_fraudster=False, is_compromised=False)
        if not cls._graph.has_node(device_node):
            cls._graph.add_node(device_node, type="DEVICE", label="New Device", is_compromised=False)
        if not cls._graph.has_node(target_node):
            if target_is_user:
                cls._graph.add_node(target_node, type="USER", label=target_account, is_fraudster=False, is_compromised=False)
            else:
                cls._graph.add_node(target_node, type="ACCOUNT", label=f"Acc {target_account}", is_compromised=False)
            
        # Add temporary edges for the incoming transaction to evaluate graph threat before committing
        added_device_edge = False
        added_account_edge = False
        
        if not cls._graph.has_edge(user_node, device_node):
            cls._graph.add_edge(user_node, device_node, type="USER_DEVICE", weight=1.0)
            added_device_edge = True
            
        if not cls._graph.has_edge(user_node, target_node):
            edge_type = "USER_TRANSFER" if target_is_user else "USER_TRANSACTION"
            cls._graph.add_edge(user_node, target_node, type=edge_type, weight=1.0)
            added_account_edge = True
        
        # Identify all compromised/fraudulent nodes in the graph
        fraud_nodes = []
        for node, attrs in cls._graph.nodes(data=True):
            if attrs.get("is_fraudster") or attrs.get("is_compromised"):
                fraud_nodes.append(node)
                
        min_distance = float('inf')
        if fraud_nodes:
            # Find shortest path from our user_node to any fraud_node
            graph_view = cls._graph.to_undirected()
            for fn in fraud_nodes:
                if fn == user_node:
                    continue
                try:
                    path_len = nx.shortest_path_length(graph_view, source=user_node, target=fn)
                    if path_len < min_distance:
                        min_distance = path_len
                except nx.NetworkXNoPath:
                    continue
        # Structure checks
        is_circular = cls.detect_circular_flow(user_id)
        is_layering = cls.detect_layering(user_id)
        is_burst = cls.detect_burst_transfers(db, user_id)
        is_hub = cls.detect_hub_account(user_id)
        is_funnel = cls.detect_funnel_account(user_id)
        shared_users = cls.get_shared_device_users(user_id)

        distance_to_fraud = 1.0 / min_distance if min_distance != float('inf') else 0.0
        shared_count = float(len(shared_users))

        cls._load_model()
        combined = None
        if cls._model is not None:
            try:
                # Model features: [distance_to_fraud, is_circular, is_layering, is_burst, is_hub, is_funnel, shared_device_users_count]
                x = np.array([[
                    distance_to_fraud,
                    float(is_circular),
                    float(is_layering),
                    float(is_burst),
                    float(is_hub),
                    float(is_funnel),
                    shared_count
                ]])
                combined = float(cls._model.predict_proba(x)[0][1] * 100.0)
            except Exception as e:
                print(f"[PayShield] Graph model inference failed, using heuristic: {e}")
                combined = None
        if combined is None:
            # Score based on distance
            if min_distance == 1:
                distance_score = 100.0
            elif min_distance == 2:
                distance_score = 80.0
            elif min_distance == 3:
                distance_score = 40.0
            elif min_distance == 4:
                distance_score = 15.0
            else:
                distance_score = 0.0
            
            mule_score = 40.0 if (is_funnel or is_hub) else 0.0
            
            ring_score = 0.0
            if len(shared_users) >= 4:
                ring_score = 40.0
            elif len(shared_users) >= 2:
                ring_score = 20.0
                
            # Add risk penalties for circular flow, layering, and bursts
            penalties = 0.0
            if is_circular:
                penalties += 45.0
            if is_layering:
                penalties += 40.0
            if is_burst:
                penalties += 30.0
                
            combined_base = max(distance_score, mule_score, ring_score)
            combined = min(combined_base + penalties, 100.0)

        
        signals = {
            "circular_flow": is_circular,
            "layering": is_layering,
            "burst_transfers": is_burst,
            "hub_account": is_hub,
            "funnel_account": is_funnel,
            "shared_device": len(shared_users) >= 1
        }
        
        # Clean up temporary edges
        if added_device_edge:
            cls._graph.remove_edge(user_node, device_node)
        if added_account_edge:
            cls._graph.remove_edge(user_node, target_node)
            
        return combined, signals

    @classmethod
    def get_graph_data(cls, db: Session) -> dict:
        """
        Formats graph for frontend rendering (nodes and links compatible with React Flow / custom viz).
        """
        nodes_list = []
        edges_list = []
        
        for node, attrs in cls._graph.nodes(data=True):
            is_mule = False
            is_hub = False
            is_funnel = False
            is_circular = False
            is_layering = False
            
            node_type = attrs.get("type", "USER")
            if node_type == "USER":
                user_id = node.replace("user_", "")
                is_hub = cls.detect_hub_account(user_id)
                is_funnel = cls.detect_funnel_account(user_id)
                is_mule = is_funnel or is_hub or cls.detect_mule_pattern(user_id)
                is_circular = cls.detect_circular_flow(user_id)
                is_layering = cls.detect_layering(user_id)
                
            nodes_list.append({
                "id": node,
                "label": attrs.get("label", node),
                "type": node_type,
                "is_fraudster": attrs.get("is_fraudster", False),
                "is_compromised": attrs.get("is_compromised", False),
                "is_mule": is_mule,
                "is_hub": is_hub,
                "is_funnel": is_funnel,
                "is_circular": is_circular,
                "is_layering": is_layering
            })
            
        for u, v, attrs in cls._graph.edges(data=True):
            is_fraud_path = False
            u_attrs = cls._graph.nodes.get(u, {})
            v_attrs = cls._graph.nodes.get(v, {})
            if (u_attrs.get("is_fraudster") or u_attrs.get("is_compromised") or
                v_attrs.get("is_fraudster") or v_attrs.get("is_compromised")):
                is_fraud_path = True
                
            edges_list.append({
                "source": u,
                "target": v,
                "type": attrs.get("type", "LINK"),
                "weight": attrs.get("weight", 1.0),
                "is_fraud_path": is_fraud_path
            })
            
        return {"nodes": nodes_list, "edges": edges_list}

    @classmethod
    def register_transaction(
        cls,
        user_id: str,
        device_hash: str,
        browser: str,
        os: str,
        target_account: str,
        target_is_user: bool
    ):
        """
        Incrementally adds the scored transaction/device/user to the warm in-memory graph.
        """
        user_node = f"user_{user_id}"
        device_node = f"device_{device_hash}"
        
        # Ensure user node
        if not cls._graph.has_node(user_node):
            cls._graph.add_node(user_node, type="USER", label=user_id, is_fraudster=False, is_compromised=False)
            
        # Ensure device node and user-device edge
        if not cls._graph.has_node(device_node):
            cls._graph.add_node(device_node, type="DEVICE", label=f"Device ({os})", is_compromised=False)
        cls._graph.add_edge(user_node, device_node, type="USER_DEVICE", weight=1.0)
        
        # Target node & edge
        if target_is_user:
            target_node = f"user_{target_account}"
            if not cls._graph.has_node(target_node):
                cls._graph.add_node(target_node, type="USER", label=target_account, is_fraudster=False, is_compromised=False)
            cls._graph.add_edge(user_node, target_node, type="USER_TRANSFER", weight=1.0)
        else:
            target_node = f"account_{target_account}"
            if not cls._graph.has_node(target_node):
                cls._graph.add_node(target_node, type="ACCOUNT", label=f"Acc {target_account[-4:] if len(target_account) > 4 else target_account}", is_compromised=False)
            cls._graph.add_edge(user_node, target_node, type="USER_TRANSACTION", weight=1.0)
            
        cls.save_graph()
