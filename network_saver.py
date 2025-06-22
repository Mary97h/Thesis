from mininet.log import info
import os
import json
import numpy as np
import csv


def is_valid_node(name):
    """Check if node is a switch or AP (excluding stations and s0)"""
    return ((name.startswith('s')) or name.startswith('ap')) and not name.startswith('sta')


def save_topology_to_file(net, filename="topology.json"):
    """Save network topology to JSON file and generate adjacency matrix"""
    info("[*] Saving topology to JSON file...\n")
    
    # Get valid switches and APs
    switches_and_aps = sorted([name for name in net.keys() if is_valid_node(name)])
    
    # Extract links
    links = []
    seen_links = set()

    for name, node in net.items():
        if not is_valid_node(name) or not hasattr(node, 'intfs'):
            continue
            
        for intf in node.intfs.values():
            if not (hasattr(intf, 'link') and intf.link and 
                   hasattr(intf.link, 'intf1') and hasattr(intf.link, 'intf2')):
                continue
                
            link = intf.link
            if id(link) in seen_links:
                continue
                
            # Get source and destination nodes
            try:
                src_node = link.intf1.node.name if hasattr(link.intf1, 'node') else None
                dst_node = link.intf2.node.name if hasattr(link.intf2, 'node') else None
                
                if not (src_node and dst_node and 
                       is_valid_node(src_node) and is_valid_node(dst_node)):
                    continue
                    
            except AttributeError as e:
                info(f"Error accessing node names: {e}\n")
                continue
            
            # Get port numbers
            src_port = dst_port = -1
            try:
                if hasattr(link.intf1.node, 'ports') and link.intf1 in link.intf1.node.ports:
                    src_port = link.intf1.node.ports[link.intf1]
                if hasattr(link.intf2.node, 'ports') and link.intf2 in link.intf2.node.ports:
                    dst_port = link.intf2.node.ports[link.intf2]
            except Exception as e:
                info(f"Error getting ports for link {src_node}-{dst_node}: {e}\n")
        
            links.append({
                "src": src_node,
                "dst": dst_node,
                "src_port": src_port,
                "dst_port": dst_port,
                "bw": getattr(link, 'bw', 100),
                "delay": getattr(link, 'delay', '5ms')
            })
            seen_links.add(id(link))
            
    info(f"Found {len(switches_and_aps)} switches/APs and {len(links)} links between them (stations excluded)\n")
    
    topology = {"nodes": switches_and_aps, "links": links}
    
    # Save topology file
    filepath = os.path.join(os.getcwd(), filename)
    try:
        with open(filepath, "w") as f:
            json.dump(topology, f, indent=2)
        info(f"[INFO] Topology saved to {filepath}\n")
    except Exception as e:
        info(f"*** ERROR writing topology file: {e}\n")

    # Generate adjacency matrix
    try:
        save_adjacency_matrix(topology)
    except Exception as e:
        info(f"*** ERROR generating adjacency matrix: {e}\n")
        
    return topology


def save_adjacency_matrix(topology, port_stats=None):
    """Generate and save adjacency matrix for switches and APs only"""
    info("[*] Generating adjacency matrix for switches and access points only (NO STATIONS)...\n")
    
    nodes = sorted([node for node in topology["nodes"] if is_valid_node(node)])
    info(f"Nodes in matrix (NO STATIONS): {nodes}\n")
    
    node_index = {node: idx for idx, node in enumerate(nodes)}
    adjacency_matrix = np.zeros((len(nodes), len(nodes)), dtype=float)
    
    # Build adjacency matrix from links
    for link in topology["links"]:
        src, dst = link["src"], link["dst"]
        
        if src.startswith('sta') or dst.startswith('sta'):
            info(f"Skipping station link: {src} -> {dst}\n")
            continue
        
        if src in node_index and dst in node_index:
            i, j = node_index[src], node_index[dst]
            bandwidth = link.get("bw", 100)
            adjacency_matrix[i][j] = adjacency_matrix[j][i] = bandwidth
            info(f"Added link {src}({i}) <-> {dst}({j}) with bandwidth {bandwidth}\n")
        else:
            info(f"Warning: Link {src} -> {dst} contains nodes not in matrix\n")
    
    # Update with port statistics if provided
    if port_stats:
        info("Updating matrix with port statistics (excluding stations)...\n")
        
        # Create port-to-node mapping
        port_map = {}
        for link in topology["links"]:
            src, dst = link["src"], link["dst"]
            if src.startswith('sta') or dst.startswith('sta'):
                continue
                
            src_port, dst_port = link.get("src_port"), link.get("dst_port")
            if src_port is not None and src_port != -1:
                port_map[(src, src_port)] = dst
            if dst_port is not None and dst_port != -1:
                port_map[(dst, dst_port)] = src
        
        # Update matrix with port statistics
        for node_name, ports in port_stats.items():
            if node_name.startswith('sta') or node_name not in node_index:
                continue
                
            for port_no, stats in ports.items():
                dest_node = port_map.get((node_name, port_no))
                if dest_node and not dest_node.startswith('sta') and dest_node in node_index:
                    total_mbps = max(
                        stats.get('tx_mbps', 0) + stats.get('rx_mbps', 0),
                        adjacency_matrix[node_index[node_name]][node_index[dest_node]]
                    )
                    i, j = node_index[node_name], node_index[dest_node]
                    adjacency_matrix[i][j] = adjacency_matrix[j][i] = total_mbps
    
    info("Adjacency matrix generated successfully (switches and APs only - NO STATIONS)\n")
    
    # Print matrix
    info("Generated adjacency matrix:\n")
    for i, node in enumerate(nodes):
        row_str = f"{node}: " + " ".join(f"{val:6.1f}" for val in adjacency_matrix[i])
        info(row_str + "\n")

    # Save to CSV
    csv_filename = os.path.join(os.getcwd(), "bandwidth_matrix_switches_aps_no_stations.csv")
    with open(csv_filename, mode='w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([""] + nodes)
        for i, node in enumerate(nodes):
            writer.writerow([node] + [f"{x:.2f}" for x in adjacency_matrix[i]])
    
    info(f"\n[INFO] Bandwidth matrix (switches and APs only - NO STATIONS) saved to {csv_filename}\n")
    return adjacency_matrix