import re
import json
import numpy as np
import csv
from collections import defaultdict

def get_topology_matrix():
    topology_links = [
        "net.addLink(s1, s5)", "net.addLink(s2, s4)", "net.addLink(s1, s3)", "net.addLink(s2, s6)",
        "net.addLink(s3, s8)", "net.addLink(s4, s7)", "net.addLink(s3, s7)", "net.addLink(s4, s8)",
        "net.addLink(s5, s9)", "net.addLink(s6, s10)", "net.addLink(s5, s10)", "net.addLink(s6, s9)",
        "net.addLink(s7, ap1)", "net.addLink(s8, ap2)", "net.addLink(s9, ap3)", "net.addLink(s10, ap4)",
        "net.addLink(s1, s0)", "net.addLink(s0, s2)", "net.addLink(s0, h0)", "net.addLink(ap5, s7)",
        "net.addLink(ap6, s8)", "net.addLink(ap7, s9)", "net.addLink(ap8, s10)", "net.addLink(h8, s3)",
        "net.addLink(h1, s7)", "net.addLink(h5, s4)", "net.addLink(h2, s8)", "net.addLink(h6, s5)",
        "net.addLink(h3, s9)", "net.addLink(s6, h7)", "net.addLink(s10, h4)"
    ]

    adjacency = defaultdict(list)
    nodes = set()

    for line in topology_links:
        match = re.findall(r"addLink\((\w+),\s*(\w+)\)", line)
        if match:
            node1, node2 = match[0]
            adjacency[node1].append(node2)
            adjacency[node2].append(node1)
            nodes.add(node1)
            nodes.add(node2)

    try:
        from mininet.wifi.net import Mininet_wifi
        net = Mininet_wifi()  

        for sta in net.stations:
            associated = sta.params.get('associatedTo')
            if associated:
                ap = associated[0].name
                sta_name = sta.name
                adjacency[sta_name].append(ap)
                adjacency[ap].append(sta_name)
                nodes.add(sta_name)
                nodes.add(ap)
    except Exception as e:
        print("Warning: Failed to read dynamic wireless state")
        print(e)

    links = []
    processed_pairs = set() 
    
    for src, destinations in adjacency.items():
        for dst in destinations:
        
            link_id = tuple(sorted([src, dst]))
            if link_id not in processed_pairs:
                links.append({
                    "src": src,
                    "dst": dst,
                    "bw": 10,  
                    "delay": "5ms" 
                })
                processed_pairs.add(link_id)

    topology = {
        "nodes": sorted(list(nodes)),
        "links": links
    }
    
    return topology

def save_topology_to_file(filepath="/tmp/topology.json"):
    topology = get_topology_matrix()
    with open(filepath, "w") as f:
        json.dump(topology, f, indent=2)
    print(f"Topology saved to {filepath}")
    

    save_adjacency_matrix(topology)

def save_adjacency_matrix(topology):
   
    all_nodes = topology["nodes"]
    node_index = {node: idx for idx, node in enumerate(all_nodes)}
    matrix_size = len(all_nodes)
    adjacency_matrix = np.zeros((matrix_size, matrix_size), dtype=int)

    for link in topology["links"]:
        src = link["src"]
        dst = link["dst"]
        i = node_index[src]
        j = node_index[dst]
        adjacency_matrix[i][j] = 1
        adjacency_matrix[j][i] = 1  

    # Print matrix
    print("\nAdjacency Matrix:")
    print("    " + "  ".join(all_nodes))
    for i, node in enumerate(all_nodes):
        row = "  ".join(str(x) for x in adjacency_matrix[i])
        print(f"{node:<4} {row}")

    csv_filename = "adjacency_matrix.csv"
    with open(csv_filename, mode='w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([""] + all_nodes)
        for i, node in enumerate(all_nodes):
            writer.writerow([node] + list(adjacency_matrix[i]))

    print(f"\nAdjacency matrix saved to {csv_filename}")

if __name__ == "__main__":
    save_topology_to_file()