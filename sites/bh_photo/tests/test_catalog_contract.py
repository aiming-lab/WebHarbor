"""Keep the comparison field consistent with the visible effective resolution."""
import json
import re
import unittest
from pathlib import Path


class CatalogContractTests(unittest.TestCase):
    def test_all_mirrorless_cameras_have_the_correct_effective_megapixels(self):
        source = Path(__file__).resolve().parents[1] / 'source_catalog.json'
        catalog = json.loads(source.read_text())
        cameras = [p for p in catalog['products'] if p['subcategory_slug'] == 'mirrorless-cameras']
        self.assertTrue(cameras)
        for product in cameras:
            with self.subTest(product=product['name']):
                values = set()
                for spec in product['specs']:
                    if spec['label'] == 'Effective Sensor Resolution':
                        pattern = r'(\d+(?:\.\d+)?)\s*Megapixel'
                    elif spec['label'] == 'Sensor Resolution':
                        pattern = r'Effective:\s*(\d+(?:\.\d+)?)\s*Megapixel'
                    else:
                        continue
                    match = re.search(pattern, spec['value'], re.I)
                    if match:
                        values.add(float(match[1]))
                self.assertEqual(values, {product['megapixels']})
                self.assertNotIn('Extension Tube', product['name'])


if __name__ == '__main__':
    unittest.main()
