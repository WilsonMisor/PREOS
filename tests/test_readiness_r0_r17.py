import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReadinessR0R17Tests(unittest.TestCase):
    def test_readiness_gates_map_to_existing_preos_super_gates(self):
        readiness = json.loads((ROOT / "references" / "readiness" / "r0-r17-gates.json").read_text(encoding="utf-8"))
        production = json.loads((ROOT / "references" / "gates" / "production-gates.json").read_text(encoding="utf-8"))
        gates = readiness["gates"]
        self.assertEqual(readiness["count"], 18)
        self.assertEqual([gate["readiness_gate_id"] for gate in gates], [f"R{i}" for i in range(18)])
        self.assertEqual([gate["source_gate_id"] for gate in gates], [f"G{i}" for i in range(18)])
        super_gate_ids = {gate["id"] for gate in production["gates"]}
        self.assertEqual(super_gate_ids, {f"G{i}" for i in range(12)})
        for gate in gates:
            mapped = set(gate["mapped_preos_super_gates"])
            self.assertTrue(mapped)
            self.assertTrue(mapped <= super_gate_ids)

    def test_readiness_domain_registry_is_bounded(self):
        registry = json.loads((ROOT / "references" / "readiness" / "domain-registry.json").read_text(encoding="utf-8"))
        domains = registry["domains"]
        self.assertEqual(registry["count"], 36)
        self.assertEqual(len(domains), 36)
        self.assertEqual(len({domain["id"] for domain in domains}), 36)
        self.assertTrue(all(domain["id"].startswith("RD-") for domain in domains))


if __name__ == "__main__":
    unittest.main()
