# -*- coding: utf-8 -*-
import copy
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import app as factory


class ModelSelectionTests(unittest.TestCase):
    def setUp(self):
        self.original_config = copy.deepcopy(factory.CONFIG)
        self.client = factory.app.test_client()

    def tearDown(self):
        factory.CONFIG.clear()
        factory.CONFIG.update(self.original_config)

    def test_exact_h3_models_override_legacy_profile(self):
        factory.CONFIG.update({
            'h3_fl2va_model': 'custom-fl2va.safetensors',
            'h3_ref2va_model': 'custom-ref2va.safetensors',
        })
        self.assertEqual(factory.get_h3_model_name('t2v'), 'custom-fl2va.safetensors')
        self.assertEqual(factory.get_h3_model_name('i2v'), 'custom-fl2va.safetensors')
        self.assertEqual(factory.get_h3_model_name('r2v'), 'custom-ref2va.safetensors')

    def test_missing_exact_h3_model_does_not_silently_fallback(self):
        factory.CONFIG['h3_fl2va_model'] = 'chosen-fl2va.safetensors'
        with self.assertRaisesRegex(ValueError, 'chosen-fl2va'):
            factory.resolve_h3_model_name('t2v', ['different-fl2va.safetensors'])

    def test_local_llm_catalog_excludes_mmproj(self):
        with tempfile.TemporaryDirectory() as directory:
            open(os.path.join(directory, 'model-a.gguf'), 'wb').close()
            open(os.path.join(directory, 'mmproj-model-a.gguf'), 'wb').close()
            with patch.object(factory, 'QWEN_MODEL_DIR', directory):
                factory.CONFIG['qwen_model_path'] = os.path.join(directory, 'model-a.gguf')
                models = factory.local_llm_models()
        self.assertEqual([item['label'] for item in models], ['model-a.gguf'])

    @patch.object(factory, 'comfy_loader_models', return_value=[
        'Qwen\\qwen-image-2512-Q4_K_S.gguf', 'Flux\\flux-dev.gguf'])
    def test_image_catalog_filters_models_by_adapter_prefix(self, _models):
        qwen = next(item for item in factory.image_workflow_catalog()
                    if item['id'] == 't2i_qwen2512.json')
        self.assertEqual(qwen['models'], ['Qwen\\qwen-image-2512-Q4_K_S.gguf'])

    @patch.object(factory, 'comfy_loader_models', return_value=['Qwen\\alternative.gguf'])
    def test_selected_image_model_is_written_to_workflow(self, _models):
        factory.CONFIG['image_model'] = 'Qwen\\alternative.gguf'
        workflow = factory.load_t2i_workflow('t2i_qwen2512.json')
        selected = factory.apply_image_model(workflow)
        self.assertEqual(selected, 'Qwen\\alternative.gguf')
        self.assertEqual(workflow['json']['133']['inputs']['unet_name'], selected)

    @patch.object(factory, 'image_workflow_catalog', return_value=[])
    @patch.object(factory, 'comfy_unet_models', return_value=['minimax_h3_fl2va_test.safetensors'])
    @patch.object(factory, 'local_llm_models', return_value=[])
    @patch.object(factory.requests, 'get')
    def test_models_api_groups_available_choices(self, get, _local, _video, _image):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'data': [{'id': 'qwen-local'}]}
        get.return_value = response
        data = self.client.get('/api/models').get_json()
        self.assertEqual(data['llm']['service_models'], ['qwen-local'])
        self.assertEqual(data['video']['fl2va'], ['minimax_h3_fl2va_test.safetensors'])

    @patch.object(factory, 'save_config')
    def test_config_rejects_unknown_image_workflow(self, _save):
        response = self.client.post('/api/config', json={'image_workflow': '../unsafe.json'})
        self.assertEqual(response.status_code, 400)

    @patch.object(factory, 'save_config')
    def test_config_accepts_exact_model_selections(self, _save):
        response = self.client.post('/api/config', json={
            'h3_fl2va_model': 'minimax_h3_fl2va_custom.safetensors',
            'h3_ref2va_model': 'minimax_h3_ref2va_custom.safetensors',
            'image_workflow': 't2i_qwen2512.json',
            'image_model': 'Qwen\\custom.gguf',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['config']['image_model'], 'Qwen\\custom.gguf')

    def test_web_settings_expose_all_three_model_groups(self):
        with open(os.path.join(ROOT, 'index.html'), 'r', encoding='utf-8') as handle:
            page = handle.read()
        for element_id in ('cfg-local-llm-file', 'cfg-h3-fl2va', 'cfg-h3-ref2va',
                           'cfg-image-workflow', 'cfg-image-model'):
            self.assertIn(f'id="{element_id}"', page)
        self.assertIn("fetch('/api/models'", page)


if __name__ == '__main__':
    unittest.main()
