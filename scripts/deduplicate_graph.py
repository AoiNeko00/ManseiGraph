import json
import os
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "frontend", "src", "data.json")

def deduplicate():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    nodes = data["nodes"]
    links = data["links"]
    
    # 1. 이름 기반 노드 그룹핑
    name_to_nodes = defaultdict(list)
    for node in nodes:
        name_to_nodes[node["name"]].append(node)
    
    new_nodes = []
    id_map = {} # old_id -> canonical_id
    
    for name, group in name_to_nodes.items():
        # 가장 정보가 많은(설명이 긴) 노드를 대표(canonical)로 선정
        canonical_node = max(group, key=lambda n: len(n.get("description", "")))
        canonical_id = canonical_node["id"]
        
        # 그룹 내 모든 ID를 canonical_id로 매핑
        for node in group:
            id_map[node["id"]] = canonical_id
            
        new_nodes.append(canonical_node)
    
    # 2. 링크 ID 업데이트 및 중복 링크 제거
    new_links_dict = {}
    for link in links:
        # source/target이 객체인 경우와 문자열인 경우 모두 대응
        src = link["source"]["id"] if isinstance(link["source"], dict) else link["source"]
        tgt = link["target"]["id"] if isinstance(link["target"], dict) else link["target"]
        
        new_src = id_map.get(src, src)
        new_tgt = id_map.get(tgt, tgt)
        
        if new_src == new_tgt: continue # 자기 참조 제거
        
        # 방향성 없는 유일 키 생성
        link_key = tuple(sorted([new_src, new_tgt]) + [link.get("relation", "")])
        
        if link_key not in new_links_dict:
            link["source"] = new_src
            link["target"] = new_tgt
            new_links_dict[link_key] = link
            
    final_links = list(new_links_dict.values())
    
    # 3. Degree 재계산
    node_degree = defaultdict(int)
    for link in final_links:
        node_degree[link["source"]] += 1
        node_degree[link["target"]] += 1
        
    for node in new_nodes:
        node["degree"] = node_degree[node["id"]]
        
    # 4. 저장
    data["nodes"] = new_nodes
    data["links"] = final_links
    
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Deduplication Complete:")
    print(f"- Nodes: {len(nodes)} -> {len(new_nodes)}")
    print(f"- Links: {len(links)} -> {len(final_links)}")

if __name__ == "__main__":
    deduplicate()
