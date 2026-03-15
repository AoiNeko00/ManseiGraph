"""커뮤니티 탐지(community detection) 모듈.

Leiden 알고리즘을 사용하여 그래프에서 커뮤니티를 자동 탐지한다.
계층적(hierarchical) 탐지를 지원하여 다중 해상도의 커뮤니티를 생성한다.
"""

import igraph as ig
import leidenalg

from core.graph_utils import build_node_index


def build_igraph(graph: dict) -> tuple[ig.Graph, list[str]]:
    """JSON 그래프를 igraph 객체로 변환한다.

    Returns:
        (igraph.Graph, node_id_list): igraph 객체와 인덱스→노드ID 매핑 리스트.
    """
    node_index = build_node_index(graph)
    node_ids = list(node_index.keys())
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}

    edges = []
    weights = []
    for link in graph["links"]:
        src_idx = id_to_idx.get(link["source"])
        tgt_idx = id_to_idx.get(link["target"])
        if src_idx is not None and tgt_idx is not None and src_idx != tgt_idx:
            edges.append((src_idx, tgt_idx))
            weights.append(link.get("weight", 1))

    g = ig.Graph(n=len(node_ids), edges=edges, directed=False)
    g.es["weight"] = weights
    return g, node_ids


def detect_communities(
    graph: dict,
    resolution: float = 1.0,
) -> dict[str, int]:
    """Leiden 알고리즘으로 커뮤니티를 탐지한다.

    Args:
        graph: {"nodes": [...], "links": [...]} 형태의 그래프.
        resolution: Leiden 해상도 파라미터. 높을수록 작은 커뮤니티 생성.

    Returns:
        {node_id: community_index} 매핑.
    """
    ig_graph, node_ids = build_igraph(graph)

    partition = leidenalg.find_partition(
        ig_graph,
        leidenalg.RBConfigurationVertexPartition,
        weights=ig_graph.es["weight"],
        resolution_parameter=resolution,
        seed=42,
    )

    return {node_ids[i]: partition.membership[i] for i in range(len(node_ids))}


def detect_hierarchical_communities(
    graph: dict,
    resolutions: list[float] | None = None,
) -> list[dict[str, int]]:
    """다중 해상도로 계층적 커뮤니티를 탐지한다.

    Args:
        graph: 그래프 데이터.
        resolutions: 해상도 리스트. 낮은 값=큰 커뮤니티, 높은 값=작은 커뮤니티.

    Returns:
        각 해상도별 {node_id: community_index} 매핑 리스트.
    """
    if resolutions is None:
        resolutions = [0.5, 1.0, 2.0]

    return [detect_communities(graph, res) for res in resolutions]


def compute_modularity(graph: dict, membership: dict[str, int]) -> float:
    """커뮤니티 할당의 모듈러리티(modularity) 점수를 계산한다."""
    ig_graph, node_ids = build_igraph(graph)
    id_to_membership = membership
    partition_list = [id_to_membership.get(nid, 0) for nid in node_ids]

    return ig_graph.modularity(partition_list, weights=ig_graph.es["weight"])


def group_communities(
    graph: dict,
    membership: dict[str, int],
) -> dict[int, list[dict]]:
    """커뮤니티별로 소속 노드를 그룹핑한다.

    Returns:
        {community_index: [node_dict, ...]} 매핑.
    """
    node_index = build_node_index(graph)
    groups: dict[int, list[dict]] = {}

    for node_id, comm_idx in membership.items():
        node = node_index.get(node_id)
        if node is None:
            continue
        groups.setdefault(comm_idx, []).append(node)

    return groups


def merge_small_communities(
    membership: dict[str, int],
    graph: dict,
    min_size: int = 3,
) -> dict[str, int]:
    """소규모 커뮤니티를 가장 연결이 많은 이웃 커뮤니티에 병합한다.

    Args:
        membership: 노드→커뮤니티 매핑.
        graph: 그래프 데이터 (이웃 커뮤니티 판별에 사용).
        min_size: 이 크기 미만인 커뮤니티를 병합 대상으로 한다.

    Returns:
        병합된 {node_id: community_index} 매핑.
    """
    # 커뮤니티별 크기 계산
    comm_sizes: dict[int, int] = {}
    for comm_idx in membership.values():
        comm_sizes[comm_idx] = comm_sizes.get(comm_idx, 0) + 1

    # 이웃 관계 구축 (노드→이웃 노드들)
    neighbors: dict[str, list[str]] = {}
    for link in graph["links"]:
        src, tgt = link["source"], link["target"]
        neighbors.setdefault(src, []).append(tgt)
        neighbors.setdefault(tgt, []).append(src)

    result = dict(membership)

    # 고립 노드용 "uncategorized" 인덱스 (-1)
    UNCATEGORIZED = -1

    for node_id, comm_idx in membership.items():
        if comm_sizes.get(comm_idx, 0) >= min_size:
            continue

        # 이웃 노드들의 커뮤니티 투표
        neighbor_comms: dict[int, int] = {}
        for neighbor_id in neighbors.get(node_id, []):
            n_comm = result.get(neighbor_id)
            if n_comm is not None and comm_sizes.get(n_comm, 0) >= min_size:
                neighbor_comms[n_comm] = neighbor_comms.get(n_comm, 0) + 1

        if neighbor_comms:
            best_comm = max(neighbor_comms, key=neighbor_comms.get)
            result[node_id] = best_comm
        else:
            # 이웃이 없는 고립 노드 → uncategorized
            result[node_id] = UNCATEGORIZED

    return result


def get_community_links(
    graph: dict,
    membership: dict[str, int],
    community_idx: int,
) -> list[dict]:
    """특정 커뮤니티 내부의 링크만 추출한다."""
    comm_nodes = {
        nid for nid, idx in membership.items() if idx == community_idx
    }
    return [
        link for link in graph["links"]
        if link["source"] in comm_nodes and link["target"] in comm_nodes
    ]
