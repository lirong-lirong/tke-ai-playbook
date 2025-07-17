import unittest
import json
from unittest.mock import patch
import os
import sys

# Adjust the path to import the script from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import generate_config

class TestGenerateConfig(unittest.TestCase):

    def is_power_of_two(self, n):
        """Helper function to check if a number is a power of two."""
        if not isinstance(n, int) or n <= 0:
            return False
        return (n & (n - 1)) == 0

    @patch('generate_config.read_bool_param')
    @patch('generate_config.read_str_param')
    @patch('generate_config.read_json_param')
    @patch('generate_config.read_int_param')
    def test_non_pd_scenario(self, mock_read_int, mock_read_json, mock_read_str, mock_read_bool):
        """ 
        Verify that for non-pd configs, both tp and pp values in the generated
        configurations are always powers of two.
        """
        print("\n\n--- Running: test_non_pd_scenario ---")
        
        # --- Mock Configuration for this specific test ---
        def mock_json(key, default='[]'):
            if key == 'models': return ["test-model"]
            if key == 'engines': return ["test-engine"]
            if key == 'pd_enable': return [False]  # <-- Key for this test
            return json.loads(default)

        def mock_int(key, default=0):
            if key == 'node_size': return 1
            if key == 'gpu_per_node': return 8
            return default

        def mock_str(key, default=''):
            if key == 'ISL': return '0'
            if key == 'OSL': return '500'
            if key == 'requests': return '5'
            return default

        mock_read_int.side_effect = mock_int
        mock_read_json.side_effect = mock_json
        mock_read_str.side_effect = mock_str
        mock_read_bool.return_value = False

        # --- Execute & Assert ---
        json_output = generate_config.main()
        results = json.loads(json_output)
        print("Generated Configs (Non-PD):")
        print(json.dumps(results, indent=4))

        self.assertGreater(len(results), 0)
        for config in results:
            self.assertFalse(config['deploy']['pd']['enable'])
            self.assertTrue(self.is_power_of_two(config['deploy']['tp']))
            self.assertTrue(self.is_power_of_two(config['deploy']['pp']))

    @patch('generate_config.read_bool_param')
    @patch('generate_config.read_str_param')
    @patch('generate_config.read_json_param')
    @patch('generate_config.read_int_param')
    def test_pd_scenario(self, mock_read_int, mock_read_json, mock_read_str, mock_read_bool):
        """
        Verify that for pd-enabled configs, the scaling factor and replica counts
        are calculated correctly.
        """
        print("\n\n--- Running: test_pd_scenario ---")

        # --- Mock Configuration for this specific test ---
        def mock_json(key, default='[]'):
            if key == 'models': return ["test-model"]
            if key == 'engines': return ["test-engine"]
            if key == 'pd_enable': return [True]  # <-- Key for this test
            return json.loads(default)

        def mock_int(key, default=0):
            return {
                'node_size': 2, 'gpu_per_node': 8, # 16 total GPUs
                'pd_prefill_replicas': 1, 'pd_decode_replicas': 2,
                'pd_prefill_tp': 2, 'pd_decode_tp': 1,
                'pd_prefill_pp': 2, 'pd_decode_pp': 1,
            }.get(key, default)

        def mock_str(key, default=''):
            if key == 'ISL': return '0'
            if key == 'OSL': return '500'
            if key == 'requests': return '5'
            return default

        mock_read_int.side_effect = mock_int
        mock_read_json.side_effect = mock_json
        mock_read_str.side_effect = mock_str
        mock_read_bool.return_value = False

        # --- Execute & Assert ---
        json_output = generate_config.main()
        results = json.loads(json_output)
        print("Generated Configs (PD):")
        print(json.dumps(results, indent=4))

        self.assertEqual(len(results), 1)
        config = results[0]
        pd_info = config['deploy']['pd']
        self.assertTrue(pd_info['enable'])

        # Verify scaling logic: 16 GPUs / ((1*2*2) + (2*1*1)) = 16 / 6 = 2
        expected_scaling_factor = 2
        expected_prefill_replicas = 1 * expected_scaling_factor
        expected_decode_replicas = 2 * expected_scaling_factor

        self.assertEqual(pd_info['prefill']['replicas'], expected_prefill_replicas)
        self.assertEqual(pd_info['decode']['replicas'], expected_decode_replicas)

if __name__ == '__main__':
    unittest.main()