import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from requests.auth import HTTPBasicAuth


# =========================
# 閫氱敤娓呮礂
# =========================
def strip_wrapping_quotes(value: str) -> str:
    s = value.strip()
    while len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    return s


def clean_value(value: Any) -> Any:
    if isinstance(value, str):
        return strip_wrapping_quotes(value)
    if isinstance(value, list):
        return [clean_value(v) for v in value]
    if isinstance(value, dict):
        return {k: clean_value(v) for k, v in value.items()}
    return value


# =========================
# Schema 瑙ｆ瀽鏁版嵁缁撴瀯
# =========================
@dataclass
class RelationDef:
    rel_type: str
    target_type: str
    properties: Set[str] = field(default_factory=set)


@dataclass
class EntityDef:
    entity_type: str
    properties: Set[str] = field(default_factory=set)
    relations: Dict[str, RelationDef] = field(default_factory=dict)


@dataclass
class SchemaDef:
    namespace: str
    entities: Dict[str, EntityDef] = field(default_factory=dict)


def count_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


# =========================
# 绠€鍖栫増 MarkLang Parser
# 閫傞厤浣犲綋鍓?schema 椋庢牸
# =========================
def parse_schema(schema_path: Path) -> SchemaDef:
    text = schema_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    namespace: Optional[str] = None
    entities: Dict[str, EntityDef] = {}

    entity_pattern = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\([^)]+\):\s*EntityType\s*$")
    property_pattern = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\([^)]+\):\s*[A-Za-z_][A-Za-z0-9_]*\s*$")
    relation_pattern = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\([^)]+\):\s*([A-Za-z_][A-Za-z0-9_]*)\s*$")

    current_entity: Optional[EntityDef] = None
    current_entity_indent: Optional[int] = None

    current_section: Optional[str] = None
    current_section_indent: Optional[int] = None

    current_relation: Optional[RelationDef] = None
    current_relation_indent: Optional[int] = None

    in_relation_properties = False
    relation_properties_indent: Optional[int] = None

    for raw_line in lines:
        if not raw_line.strip():
            continue

        stripped = raw_line.strip()
        indent = count_indent(raw_line)

        if stripped.startswith("//") or stripped.startswith("#"):
            continue

        if stripped.startswith("namespace "):
            namespace = stripped.split("namespace ", 1)[1].strip()
            continue

        entity_match = entity_pattern.match(stripped)
        if entity_match:
            entity_type = entity_match.group(1)
            current_entity = EntityDef(entity_type=entity_type)
            entities[entity_type] = current_entity

            current_entity_indent = indent
            current_section = None
            current_section_indent = None
            current_relation = None
            current_relation_indent = None
            in_relation_properties = False
            relation_properties_indent = None
            continue

        if current_entity is None:
            continue

        # 閫€鍑哄綋鍓嶅疄浣撳潡
        if current_entity_indent is not None and indent <= current_entity_indent:
            current_entity = None
            current_entity_indent = None
            current_section = None
            current_section_indent = None
            current_relation = None
            current_relation_indent = None
            in_relation_properties = False
            relation_properties_indent = None
            continue

        # 瀹炰綋绾?properties / relations
        if stripped == "properties:" and (current_section is None or indent <= (current_section_indent or 10**9)):
            current_section = "properties"
            current_section_indent = indent
            current_relation = None
            current_relation_indent = None
            in_relation_properties = False
            relation_properties_indent = None
            continue

        if stripped == "relations:":
            current_section = "relations"
            current_section_indent = indent
            current_relation = None
            current_relation_indent = None
            in_relation_properties = False
            relation_properties_indent = None
            continue

        # 澶勭悊瀹炰綋灞炴€?
        if current_section == "properties":
            if current_section_indent is not None and indent <= current_section_indent:
                current_section = None
                current_section_indent = None
            else:
                prop_match = property_pattern.match(stripped)
                if prop_match:
                    prop_name = prop_match.group(1)
                    current_entity.properties.add(prop_name)
                continue

        # 澶勭悊 relations
        if current_section == "relations":
            if current_section_indent is not None and indent <= current_section_indent:
                current_section = None
                current_section_indent = None
                current_relation = None
                current_relation_indent = None
                in_relation_properties = False
                relation_properties_indent = None
                continue

            # 鏂?relation
            rel_match = relation_pattern.match(stripped)
            if rel_match and (current_relation_indent is None or indent <= current_relation_indent):
                rel_type = rel_match.group(1)
                target_type = rel_match.group(2)
                current_relation = RelationDef(rel_type=rel_type, target_type=target_type)
                current_entity.relations[rel_type] = current_relation
                current_relation_indent = indent
                in_relation_properties = False
                relation_properties_indent = None
                continue

            # relation 涓嬬殑 properties:
            if stripped == "properties:" and current_relation is not None:
                if current_relation_indent is not None and indent > current_relation_indent:
                    in_relation_properties = True
                    relation_properties_indent = indent
                    continue

            # relation properties 鍐呭
            if in_relation_properties and current_relation is not None:
                if relation_properties_indent is not None and indent <= relation_properties_indent:
                    in_relation_properties = False
                else:
                    rel_prop_match = property_pattern.match(stripped)
                    if rel_prop_match:
                        rel_prop = rel_prop_match.group(1)
                        current_relation.properties.add(rel_prop)
                    continue

    if not namespace:
        raise ValueError(f"schema file missing namespace: {schema_path}")

    return SchemaDef(namespace=namespace, entities=entities)


# =========================
# Neo4j HTTP Client
# =========================
class Neo4jHttpClient:
    def __init__(self, base_url: str, username: str, password: str, database: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.database = database
        self.commit_url = f"{self.base_url}/db/{self.database}/tx/commit"

    def run(self, statement: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "statements": [
                {
                    "statement": statement,
                    "parameters": parameters or {},
                }
            ]
        }
        resp = requests.post(
            self.commit_url,
            json=payload,
            auth=HTTPBasicAuth(self.username, self.password),
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        errors = data.get("errors", [])
        if errors:
            raise RuntimeError(f"Neo4j error: {errors}")

        results = data.get("results", [])
        if not results:
            return {"columns": [], "data": []}
        return results[0]

    def query_scalar(self, statement: str, parameters: Optional[Dict[str, Any]] = None) -> Any:
        result = self.run(statement, parameters)
        rows = result.get("data", [])
        if not rows:
            return None
        return rows[0]["row"][0]


# =========================
# JSON 璇诲叆
# =========================
def load_json(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def namespaced_label(namespace: str, short_label: str) -> str:
    return f"{namespace}.{short_label}"


# =========================
# Schema-aware 鏍￠獙
# =========================
def validate_nodes_against_schema(
    schema: SchemaDef,
    nodes: List[Dict[str, Any]],
) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    errors: List[str] = []
    node_index: Dict[str, Dict[str, Any]] = {}

    for node in nodes:
        node = clean_value(node)
        node_id = node.get("id")
        label = node.get("label")
        props = node.get("properties", {})

        if not node_id:
            errors.append(f"[NODE] missing id: {node}")
            continue
        if not label:
            errors.append(f"[NODE] missing label: id={node_id}")
            continue

        if label not in schema.entities:
            errors.append(f"[NODE] label not in schema: id={node_id}, label={label}")
            continue

        entity_def = schema.entities[label]
        allowed_props = set(entity_def.properties) | {"id", "name"}

        for prop_key in props.keys():
            if prop_key not in allowed_props:
                errors.append(
                    f"[NODE] property not allowed by schema: id={node_id}, "
                    f"label={label}, property={prop_key}"
                )

        if node_id in node_index:
            errors.append(f"[NODE] duplicate id in input nodes: id={node_id}")
        else:
            node_index[node_id] = node

    return node_index, errors


def validate_edges_against_schema(
    schema: SchemaDef,
    node_index: Dict[str, Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> List[str]:
    errors: List[str] = []

    for edge in edges:
        edge = clean_value(edge)
        edge_id = edge.get("id")
        from_id = edge.get("from")
        to_id = edge.get("to")
        from_type = edge.get("fromType")
        to_type = edge.get("toType")
        rel_type = edge.get("label")
        props = edge.get("properties", {})

        if not from_id or not to_id or not from_type or not to_type or not rel_type:
            errors.append(f"[EDGE] missing required field: edge={edge}")
            continue

        if from_id not in node_index:
            errors.append(f"[EDGE] from node id not found in nodes: edge_id={edge_id}, from={from_id}")
            continue
        if to_id not in node_index:
            errors.append(f"[EDGE] to node id not found in nodes: edge_id={edge_id}, to={to_id}")
            continue

        actual_from_type = clean_value(node_index[from_id].get("label"))
        actual_to_type = clean_value(node_index[to_id].get("label"))

        if actual_from_type != from_type:
            errors.append(
                f"[EDGE] fromType mismatch: edge_id={edge_id}, from_id={from_id}, "
                f"edge_fromType={from_type}, node_label={actual_from_type}"
            )
            continue

        if actual_to_type != to_type:
            errors.append(
                f"[EDGE] toType mismatch: edge_id={edge_id}, to_id={to_id}, "
                f"edge_toType={to_type}, node_label={actual_to_type}"
            )
            continue

        if from_type not in schema.entities:
            errors.append(f"[EDGE] fromType not in schema: edge_id={edge_id}, fromType={from_type}")
            continue

        entity_def = schema.entities[from_type]
        if rel_type not in entity_def.relations:
            errors.append(
                f"[EDGE] relation not declared in schema: edge_id={edge_id}, "
                f"fromType={from_type}, relType={rel_type}"
            )
            continue

        rel_def = entity_def.relations[rel_type]
        if rel_def.target_type != to_type:
            errors.append(
                f"[EDGE] relation target mismatch: edge_id={edge_id}, "
                f"fromType={from_type}, relType={rel_type}, "
                f"schema_toType={rel_def.target_type}, edge_toType={to_type}"
            )
            continue

        allowed_rel_props = set(rel_def.properties)
        for prop_key in props.keys():
            if prop_key not in allowed_rel_props:
                errors.append(
                    f"[EDGE] relation property not allowed by schema: edge_id={edge_id}, "
                    f"relType={rel_type}, property={prop_key}"
                )

    return errors


# =========================
# 鍐欏叆 Neo4j
# =========================
def create_constraints(client: Neo4jHttpClient, schema: SchemaDef) -> None:
    for short_label in sorted(schema.entities.keys()):
        label = namespaced_label(schema.namespace, short_label)
        safe_name = f"{schema.namespace}_{short_label}_id_unique".replace(".", "_")
        cypher = f"""
        CREATE CONSTRAINT `{safe_name}` IF NOT EXISTS
        FOR (n:`{label}`)
        REQUIRE n.id IS UNIQUE
        """
        client.run(cypher)


def merge_node(client: Neo4jHttpClient, schema: SchemaDef, node: Dict[str, Any]) -> None:
    node = clean_value(node)
    raw_id = node["id"]
    raw_name = node.get("name")
    short_label = node["label"]
    label = namespaced_label(schema.namespace, short_label)

    props = clean_value(node.get("properties", {}))
    props["id"] = raw_id
    if raw_name is not None:
        props["name"] = raw_name

    cypher = f"""
    MERGE (n:Entity:`{label}` {{id: $id}})
    SET n += $props
    RETURN n.id
    """
    client.run(cypher, {"id": raw_id, "props": props})


def merge_edge(client: Neo4jHttpClient, schema: SchemaDef, edge: Dict[str, Any]) -> None:
    edge = clean_value(edge)

    from_id = edge["from"]
    to_id = edge["to"]
    rel_type = edge["label"]
    from_type = edge["fromType"]
    to_type = edge["toType"]
    props = clean_value(edge.get("properties", {}))

    from_label = namespaced_label(schema.namespace, from_type)
    to_label = namespaced_label(schema.namespace, to_type)

    cypher = f"""
    MATCH (a:Entity:`{from_label}` {{id: $from_id}})
    MATCH (b:Entity:`{to_label}` {{id: $to_id}})
    MERGE (a)-[r:`{rel_type}`]->(b)
    SET r += $props
    RETURN type(r)
    """
    client.run(
        cypher,
        {
            "from_id": from_id,
            "to_id": to_id,
            "props": props,
        },
    )


def clear_database(client: Neo4jHttpClient) -> None:
    client.run("MATCH (n) DETACH DELETE n")


def print_stats(client: Neo4jHttpClient) -> None:
    total_nodes = client.query_scalar("MATCH (n) RETURN count(n)")
    total_edges = client.query_scalar("MATCH ()-[r]->() RETURN count(r)")
    distinct_ids = client.query_scalar("MATCH (n) RETURN count(DISTINCT n.id)")
    print(f"[STATS] total_nodes = {total_nodes}")
    print(f"[STATS] total_edges = {total_edges}")
    print(f"[STATS] distinct_ids = {distinct_ids}")




def discover_default_schema() -> Path:
    schema_dir = Path("schema")
    if not schema_dir.exists():
        raise FileNotFoundError("schema directory not found: ./schema")
    candidates = sorted(schema_dir.glob("*.schema"))
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise FileNotFoundError("no .schema file found under ./schema")
    raise FileNotFoundError(f"multiple .schema files found under ./schema, please pass --schema explicitly: {[str(p) for p in candidates]}")


def resolve_runtime_targets(schema_arg: Optional[str], database_arg: Optional[str]) -> Tuple[Path, str]:
    schema_path = Path(schema_arg) if schema_arg else discover_default_schema()
    if not schema_path.exists():
        raise FileNotFoundError(f"schema file not found: {schema_path}")
    schema = parse_schema(schema_path)
    database = database_arg or schema.namespace
    return schema_path, database

# =========================
# Main
# =========================
def main() -> int:
    print("[INFO] schema-aware importer started...")

    parser = argparse.ArgumentParser(description="Schema-aware structured MERGE importer for SPG instance graph.")
    parser.add_argument("--base-url", default="http://localhost:7474", help="Neo4j HTTP base URL")
    parser.add_argument("--username", default="neo4j", help="Neo4j username")
    parser.add_argument("--password", default="neo4j@openspg", help="Neo4j password")
    parser.add_argument("--database", default=None, help="Neo4j database name; defaults to schema namespace")
    parser.add_argument("--schema", default=None, help="Path to schema file; defaults to the only .schema file under ./schema")
    parser.add_argument("--nodes", default="builder/data/nodes_kag.json", help="Path to nodes_kag.json")
    parser.add_argument("--edges", default="builder/data/edges_kag.json", help="Path to edges_kag.json")
    parser.add_argument("--clear", action="store_true", help="Clear database before import")
    args = parser.parse_args()

    try:
        schema_path, resolved_database = resolve_runtime_targets(args.schema, args.database)
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1

    nodes_path = Path(args.nodes)
    edges_path = Path(args.edges)

    if not nodes_path.exists():
        print(f"[ERROR] nodes file not found: {nodes_path}")
        return 1
    if not edges_path.exists():
        print(f"[ERROR] edges file not found: {edges_path}")
        return 1

    schema = parse_schema(schema_path)
    print(f"[INFO] parsed schema namespace = {schema.namespace}")
    print(f"[INFO] resolved neo4j database = {resolved_database}")
    print(f"[INFO] resolved schema path = {schema_path}")
    print(f"[INFO] parsed schema entity types = {len(schema.entities)}")

    nodes = load_json(nodes_path)
    edges = load_json(edges_path)

    print(f"[INFO] loaded nodes = {len(nodes)}")
    print(f"[INFO] loaded edges = {len(edges)}")

    node_index, node_errors = validate_nodes_against_schema(schema, nodes)
    edge_errors = validate_edges_against_schema(schema, node_index, edges)

    all_errors = node_errors + edge_errors
    if all_errors:
        print(f"[ERROR] schema validation failed, total errors = {len(all_errors)}")
        for item in all_errors[:100]:
            print(f"  - {item}")
        if len(all_errors) > 100:
            print("  ...")
        return 2

    print("[INFO] schema validation passed.")

    client = Neo4jHttpClient(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        database=resolved_database,
    )

    if args.clear:
        print(f"[WARN] clearing target database: {resolved_database}")
        clear_database(client)

    print("[INFO] creating constraints...")
    create_constraints(client, schema)

    print("[INFO] importing nodes...")
    for idx, node in enumerate(nodes, start=1):
        merge_node(client, schema, node)
        if idx % 20 == 0 or idx == len(nodes):
            print(f"[INFO] nodes imported: {idx}/{len(nodes)}")

    print("[INFO] importing edges...")
    for idx, edge in enumerate(edges, start=1):
        merge_edge(client, schema, edge)
        if idx % 50 == 0 or idx == len(edges):
            print(f"[INFO] edges imported: {idx}/{len(edges)}")

    print_stats(client)
    print("[DONE] schema-aware structured MERGE import finished.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] aborted by user.")
        raise SystemExit(130)
    except Exception as e:
        print(f"[FATAL] {type(e).__name__}: {e}")
        raise
