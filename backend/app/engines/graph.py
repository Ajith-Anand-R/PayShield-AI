import networkx as nx
import os
import pickle
from sqlalchemy.orm import Session
from ..models.models import GraphEdge, User, Device, Transaction

class FraudGraphEngine:
    _graph = nx.DiGraph()
    GRAPH_CACHE_PATH = "payshield_graph.pkl"

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
    def detect_mule_pattern(cls, user_id: str) -> bool:
        """High in-degree (many senders) + low out-degree (one or two receivers) = mule"""
        node = f"user_{user_id}"
        if not cls._graph.has_node(node):
            return False
        in_deg = cls._graph.in_degree(node)
        out_deg = cls._graph.out_degree(node)
        return in_deg > 5 and out_deg <= 2

    @classmethod
    def get_shared_device_users(cls, user_id: str) -> list:
        """Find all other users sharing a device with this user"""
        node = f"user_{user_id}"
        shared = set()
        neighbors = set(cls._graph.predecessors(node)) | set(cls._graph.successors(node))
        for neighbor in neighbors:
            if cls._graph.nodes.get(neighbor, {}).get("type") == "DEVICE":
                device_neighbors = set(cls._graph.predecessors(neighbor)) | set(cls._graph.successors(neighbor))
                for other in device_neighbors:
                    if other != node and cls._graph.nodes.get(other, {}).get("type") == "USER":
                        shared.add(other.replace("user_", ""))
        return list(shared)

    @classmethod
    def calculate_risk(cls, db: Session, user_id: str, device_hash: str, target_account: str) -> float:
        """
        Evaluates relationships between user, device, and target account.
        Checks closeness to known fraud nodes or clusters.
        Returns a graph risk score between 0 and 100.
        """
        # Sync graph dynamically to ensure real-time accuracy
        cls.sync_graph_from_db(db)
        
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
                
        if not fraud_nodes:
            # Clean up temporary edges
            if added_device_edge:
                cls._graph.remove_edge(user_node, device_node)
            if added_account_edge:
                cls._graph.remove_edge(user_node, target_node)
            return 0.0  # No known fraud in the system yet
            
        # Find shortest path from our user_node to any fraud_node
        min_distance = float('inf')
        closest_fraud_node = None
        graph_view = cls._graph.to_undirected()
        
        for fn in fraud_nodes:
            # Skip if we are comparing to ourselves (though we are not marked fraudster yet)
            if fn == user_node:
                continue
            try:
                path_len = nx.shortest_path_length(graph_view, source=user_node, target=fn)
                if path_len < min_distance:
                    min_distance = path_len
                    closest_fraud_node = fn
            except nx.NetworkXNoPath:
                continue
                
        # Clean up temporary edges
        if added_device_edge:
            cls._graph.remove_edge(user_node, device_node)
        if added_account_edge:
            cls._graph.remove_edge(user_node, target_node)
        
        # Score based on distance
        # Distance = 1: The user node ITSELF is marked fraudster or device is untrusted (100 risk)
        # Distance = 2: Shared device or account with a fraudster! (e.g. UserA -> DeviceX <- FraudsterB) (80 risk)
        # Distance = 3: Compromised circle (e.g. UserA -> AccY <- UserC -> DeviceZ <- FraudsterB) (40 risk)
        # Distance >= 4: Low link risk (0 risk)
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
        
        mule_score = 40.0 if cls.detect_mule_pattern(user_id) else 0.0
        
        shared_users = cls.get_shared_device_users(user_id)
        shared_flagged = sum(1 for u in shared_users if cls._graph.nodes.get(f"user_{u}", {}).get("is_fraudster"))
        ring_score = 0.0
        if len(shared_users) >= 4:
            ring_score = 40.0
        elif len(shared_users) >= 2:
            ring_score = 20.0
        
        combined = max(distance_score, mule_score, ring_score)
        return combined

    @classmethod
    def get_graph_data(cls, db: Session) -> dict:
        """
        Formats graph for frontend rendering (nodes and links compatible with React Flow / custom viz).
        """
        cls.sync_graph_from_db(db)
        
        nodes_list = []
        edges_list = []
        
        for node, attrs in cls._graph.nodes(data=True):
            nodes_list.append({
                "id": node,
                "label": attrs.get("label", node),
                "type": attrs.get("type", "USER"),
                "is_fraudster": attrs.get("is_fraudster", False),
                "is_compromised": attrs.get("is_compromised", False)
            })
            
        for u, v, attrs in cls._graph.edges(data=True):
            edges_list.append({
                "source": u,
                "target": v,
                "type": attrs.get("type", "LINK"),
                "weight": attrs.get("weight", 1.0)
            })
            
        return {"nodes": nodes_list, "edges": edges_list}
