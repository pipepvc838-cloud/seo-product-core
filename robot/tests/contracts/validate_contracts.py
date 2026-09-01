import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts" / "execution-model.v1.json"
FIXTURES = Path(__file__).with_name("fixtures.v1.json")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def has_cycle(tasks):
    graph = {t["task_id"]: list(t.get("dependencies", [])) for t in tasks}
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            return True
        if node in visited:
            return False
        if node not in graph:
            return False
        visiting.add(node)
        for dep in graph[node]:
            if dep not in graph:
                raise AssertionError(f"missing dependency: {dep}")
            if visit(dep):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(n) for n in graph)


def main():
    c = load(CONTRACT)
    f = load(FIXTURES)

    assert c["contract_version"] == "robot-execution-model.v1"
    assert c["authority"]["backend_contract_handoff"] == "SRC-CONTRACT-PM01-BE-001"
    assert c["authority"]["backend_repository_access"] is False
    assert c["backend_compatibility"]["accepted_shapes"] == ["request.v1", "result.v1", "error.v1"]

    valid = f["valid_dag"]
    assert not has_cycle(valid)
    assert has_cycle(f["cycle"])

    by_id = {t["task_id"]: t for t in valid}
    ready = [
        t for t in valid
        if t["state"] == "READY"
        and all(by_id[d]["state"] == "DONE" for d in t["dependencies"])
    ]
    ordered = [t["task_id"] for t in sorted(ready, key=lambda x: (x["sequence"], x["task_id"]))]
    assert ordered == f["ordering_expected"]

    transitions = c["transitions"]
    for case in f["transition_cases"]:
        actual = case["to"] in transitions[case["from"]]
        assert actual is case["valid"], case

    allowed_retry = set(c["retry"]["allowed_classes"])
    for case in f["retry_cases"]:
        assert (case["class"] in allowed_retry) is case["retry"], case

    for case in f["idempotency_cases"]:
        actual = case["state"] == "READY"
        assert actual is case["execute"], case

    for case in f["recovery_cases"]:
        actual = not case["prior_effect_complete"]
        assert actual is case["replay"], case

    assert c["retry"]["max_attempts"] >= 1
    assert "queue" in c["forbidden_runtime_complexity"]
    assert "worker" in c["forbidden_runtime_complexity"]
    assert c["recovery"]["replay_completed_effects"] is False
    print("ROBOT CONTRACT TESTS: PASS")


if __name__ == "__main__":
    main()
