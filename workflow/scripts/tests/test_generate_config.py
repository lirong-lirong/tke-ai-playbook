import unittest
import json
from unittest.mock import patch
import os
import sys
import itertools
import yaml

# Adjust the path to import the script from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import generate_config

class TestFinalGenerateConfig(unittest.TestCase):

    @patch('generate_config.read_config_from_yaml')
    def test_scenario_logic_v2(self, mock_read_yaml):
        """
        Verify the final, most flexible logic:
        - Scenarios inherit and override common config.
        - Scenarios can have their own model/engine lists to override common.
        - Scenarios without model/engine lists use the common ones.
        """
        print("\n\n--- Running: test_final_scenario_logic_v2 ---")

        # --- Mock Configuration Input ---
        mock_input_data = {
            'common': {
                'metadata': {'node_size': 2, 'gpu_per_node': 8},
                'models': ["common-model-A", "common-model-B"],
                'engines': ["common-engine-X"],
                'test': {'isl': 128}
            },
            'scenarios': [
                # Scenario 1: Inherits common metadata and models/engines
                {
                    'name': "regression",
                    'pd_enable': False,
                    'tp': 8, 'pp': 2,
                },
                # Scenario 2: Overrides metadata and model/engine lists
                {
                    'name': "override-list",
                    'metadata': {'node_size': 1, 'gpu_per_node': 4},
                    'models': ["scenario-model-C"],
                    'engines': ["scenario-engine-Y"],
                    'pd_enable': False,
                    'tp': 4, 'pp': 1,
                },
                # Scenario 3: Inherits common metadata, overrides with single model/engine
                {
                    'name': "override-string",
                    'model': "scenario-model-D",
                    'engine': "scenario-engine-Z",
                    'pd_enable': True,
                }
            ]
        }
        mock_read_yaml.return_value = mock_input_data

        # --- Execute ---
        json_output = generate_config.main()
        results = json.loads(json_output)
        print("Generated Configs (Final Logic v2):")
        print(json.dumps(results, indent=4))

        # --- Verification ---
        self.assertEqual(len(results), 4, "Should generate 2 + 1 + 1 = 4 total configurations")

        # 1. Verify Regression Scenario (2 configs)
        regression_configs = [c for c in results if "regression" in c['metadata']['name']]
        self.assertEqual(len(regression_configs), 2)
        self.assertEqual(regression_configs[0]['deploy']['model']['name'], "common-model-A")
        self.assertEqual(regression_configs[1]['deploy']['model']['name'], "common-model-B")

        # 2. Verify Override List Scenario (1 config)
        override_list_configs = [c for c in results if "override-list" in c['metadata']['name']]
        self.assertEqual(len(override_list_configs), 1)
        self.assertEqual(override_list_configs[0]['deploy']['model']['name'], "scenario-model-C")
        self.assertEqual(override_list_configs[0]['deploy']['engine']['name'], "scenario-engine-Y")

        # 3. Verify Override String Scenario (1 config)
        override_string_configs = [c for c in results if "override-string" in c['metadata']['name']]
        self.assertEqual(len(override_string_configs), 1)
        self.assertTrue(override_string_configs[0]['deploy']['pd']['enable'])
        self.assertEqual(override_string_configs[0]['deploy']['model']['name'], "scenario-model-D")

if __name__ == '__main__':
    unittest.main()
