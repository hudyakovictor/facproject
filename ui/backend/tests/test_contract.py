from __future__ import annotations
import unittest
from dpo.contract import InterfaceContract

class ContractTests(unittest.TestCase):
    def test_contract_spec_and_validation(self) -> None:
        contract = InterfaceContract()
        spec = contract.get_spec()
        self.assertIn("entities", spec)

        # Valid payload
        errs = contract.validate_payload("RunGroup", {"id": "g-1", "status": "candidate", "members": {}})
        self.assertEqual(errs, [])

        # Invalid payload (missing required field and bad enum)
        errs2 = contract.validate_payload("RunGroup", {"id": "g-2", "status": "unknown_status"})
        self.assertTrue(len(errs2) > 0)

if __name__ == "__main__":
    unittest.main()
