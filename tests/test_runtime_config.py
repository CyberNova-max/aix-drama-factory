# -*- coding: utf-8 -*-
import copy
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import app as factory


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.original_config = copy.deepcopy(factory.CONFIG)
        self.client = factory.app.test_client()

    def tearDown(self):
        factory.CONFIG.clear()
        factory.CONFIG.update(self.original_config)

    @patch.object(factory.subprocess, 'Popen')
    @patch.object(factory, 'comfy_check', return_value=False)
    def test_external_comfyui_never_starts_process(self, _check, popen):
        factory.CONFIG['comfyui_runtime_mode'] = 'external'
        self.assertFalse(factory.ensure_comfyui(max_wait=1))
        popen.assert_not_called()

    @patch.object(factory.subprocess, 'Popen')
    @patch.object(factory.requests, 'get', side_effect=OSError('offline'))
    def test_external_local_llm_never_starts_process(self, _get, popen):
        factory.CONFIG.update({
            'llm_mode': 'local',
            'local_llm_runtime_mode': 'external',
            'local_llm_url': 'http://127.0.0.1:18085',
        })
        ok, message = factory._ensure_local_llm_unlocked()
        self.assertFalse(ok)
        self.assertIn('不会自动启动或停止', message)
        popen.assert_not_called()

    @patch.object(factory, 'kill_by_port')
    def test_external_services_are_never_stopped(self, kill):
        factory.CONFIG.update({
            'llm_mode': 'local',
            'local_llm_runtime_mode': 'external',
            'comfyui_runtime_mode': 'external',
        })
        factory.stop_local_llm()
        factory.stop_comfyui()
        kill.assert_not_called()
        self.assertFalse(factory.exclusive_on())

    def test_configured_ffmpeg_path_has_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'ffmpeg.exe')
            with open(path, 'wb') as stream:
                stream.write(b'test')
            factory.CONFIG['ffmpeg_path'] = path
            self.assertEqual(factory.find_ffmpeg(), os.path.normpath(path))

    @patch.object(factory, 'save_config')
    def test_config_api_validates_runtime_mode_and_url(self, _save):
        response = self.client.post('/api/config', json={'comfyui_runtime_mode': 'unsafe'})
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/config', json={'comfyui_url': 'not-a-url'})
        self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/config', json={
            'comfyui_runtime_mode': 'external',
            'comfyui_url': 'http://127.0.0.1:8190',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['config']['comfyui_runtime_mode'], 'external')

    @patch.object(factory.requests, 'get')
    def test_comfy_queue_api_proxies_configured_backend(self, get):
        upstream = Mock()
        upstream.raise_for_status.return_value = None
        upstream.json.return_value = {
            'queue_running': [[1, 'running-prompt']],
            'queue_pending': [[2, 'pending-prompt']],
        }
        get.return_value = upstream

        response = self.client.get('/api/comfy/queue')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['ok'])
        self.assertEqual(response.get_json()['queue_running'], [[1, 'running-prompt']])
        self.assertEqual(response.get_json()['queue_pending'], [[2, 'pending-prompt']])
        get.assert_called_once_with(f"{factory.comfy_url()}/queue", timeout=5)

    @patch.object(factory.requests, 'get', side_effect=OSError('offline'))
    def test_comfy_queue_api_returns_safe_empty_state_when_offline(self, _get):
        response = self.client.get('/api/comfy/queue')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['queue_running'], [])
        self.assertEqual(response.get_json()['queue_pending'], [])
        self.assertFalse(response.get_json()['ok'])

    @patch.object(factory, 'find_ffmpeg', return_value='ffmpeg.exe')
    @patch.object(factory, 'comfy_check', return_value=True)
    @patch.object(factory.requests, 'get')
    def test_preflight_reports_runtime_modes(self, get, _comfy, _ffmpeg):
        get.return_value.status_code = 200
        factory.CONFIG.update({
            'llm_mode': 'local',
            'local_llm_runtime_mode': 'external',
            'comfyui_runtime_mode': 'external',
        })
        response = self.client.get('/api/runtime/preflight')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['ready_for_story'])
        self.assertTrue(data['ready_for_video'])
        self.assertEqual(data['checks']['comfyui']['mode'], 'external')
        self.assertEqual(data['checks']['llm']['mode'], 'external')

    @patch.dict(os.environ, {
        'AIX_COMFY_START_COMMAND': '/srv/start-comfy',
        'AIX_LLM_START_COMMAND': '/srv/start-qwen',
    }, clear=False)
    @patch.object(factory, 'find_ffmpeg', return_value='/usr/bin/ffmpeg')
    @patch.object(factory, 'comfy_check', return_value=False)
    @patch.object(factory.requests, 'get', side_effect=OSError('offline'))
    def test_preflight_accepts_trusted_host_managed_services(self, _get, _comfy, _ffmpeg):
        factory.CONFIG.update({
            'llm_mode': 'local',
            'local_llm_runtime_mode': 'managed',
            'comfyui_runtime_mode': 'managed',
            'llama_server_path': 'Z:/missing/llama-server.exe',
            'qwen_model_path': 'Z:/missing/model.gguf',
            'qwen_mmproj_path': 'Z:/missing/mmproj.gguf',
        })
        data = self.client.get('/api/runtime/preflight').get_json()
        self.assertTrue(data['ready_for_story'])
        self.assertTrue(data['ready_for_video'])
        self.assertTrue(data['checks']['comfyui']['host_managed'])
        self.assertTrue(data['checks']['llm']['host_managed'])
        self.assertNotIn('files', data['checks']['llm'])
        self.assertEqual(data['messages'], [])

    def test_h3_frame_alignment_does_not_add_an_extra_block(self):
        expected = {3: 73, 5: 124, 8: 192, 10: 243, 15: 362}
        for seconds, frames in expected.items():
            with self.subTest(seconds=seconds):
                self.assertEqual(factory.h3_frames_from_duration(seconds), frames)
                self.assertEqual(frames % 17, 5)

    def test_nonverbal_placeholder_is_not_treated_as_dialogue(self):
        shot = {'action': '角色抱着肚子', 'dialogue': [
            {'speaker': '小灰', 'line': '（无台词，仅发出咕噜声）', 'tone': '自然'},
            {'speaker': '小灰', 'line': '快跑！', 'tone': '紧张'},
        ]}
        self.assertEqual(factory.shot_dialogue_lines(shot), ['快跑！'])
        self.assertTrue(factory.normalize_script_dialogue({'shots': [shot]}))
        self.assertEqual(shot['dialogue'][0]['line'], '快跑！')
        self.assertIn('咕噜声', shot['action'])

    def test_bracketed_stage_direction_is_removed_from_dialogue(self):
        shot = {'action': '角色擦拭桌面', 'dialogue': [
            {'speaker': '小灰', 'line': '小灰：（摇头，继续擦拭）', 'tone': '自然'},
        ]}
        self.assertTrue(factory.normalize_script_dialogue({'shots': [shot]}))
        self.assertEqual(shot['dialogue'], [])
        self.assertIn('摇头，继续擦拭', shot['action'])

    def test_leading_stage_direction_keeps_actual_spoken_words(self):
        shot = {'action': '', 'dialogue': [
            {'speaker': '小灰', 'line': '（喘息）快跑！', 'tone': '紧张'},
        ]}
        self.assertTrue(factory.normalize_script_dialogue({'shots': [shot]}))
        self.assertEqual(factory.shot_dialogue_lines(shot), ['快跑！'])
        self.assertIn('喘息', shot['action'])

    def test_prompt_dialogue_is_relocated_into_storyboard_once(self):
        shot = {
            'characters': ['小灰'],
            'dialogue': [{'speaker': '小灰', 'line': '我是妈妈！', 'tone': '震惊'}],
        }
        draft = (
            '【Important】\n“我是妈妈！”\n\n【Storyboard】\nShot 1 (0-3s) — close-up\n'
            'Character 1 reacts.\n\n【Character Voice】\nNatural voice.\n\n【Sound】\nroom tone\n'
            '【Forbidden】\ntext\n【Mandatory】\nspoken dialogue')
        fixed = factory.repair_prompt_dialogue_placement(draft, shot)
        self.assertEqual(fixed.count('我是妈妈！'), 1)
        storyboard = fixed[fixed.index('【Storyboard】'):fixed.index('【Character Voice】')]
        self.assertIn('我是妈妈！', storyboard)

    def test_real_short_vocal_dialogue_is_preserved(self):
        shot = {'dialogue': [{'speaker': '甲', 'line': '嗯。'}, {'speaker': '乙', 'line': '啊！'}]}
        self.assertEqual(factory.shot_dialogue_lines(shot), ['嗯。', '啊！'])

    @patch.object(factory, 'comfy_unet_models', return_value=[
        'FeiHou_MiniMax-H3_Remix_v0.6_int8_convrot_v2.safetensors',
        'minimax_h3_fl2va_pruned_fp8_scaled.safetensors',
    ])
    def test_h3_model_resolver_preserves_model_family(self, _models):
        factory.CONFIG['h3_model_profile'] = 'pruned'
        self.assertIn('Remix', factory.resolve_h3_model_name('r2v'))
        self.assertIn('fl2va', factory.resolve_h3_model_name('t2v').lower())

    @patch.object(factory.requests, 'get')
    def test_comfy_workflow_options_resolve_windows_paths_on_linux(self, get):
        schemas = {
            'UnetLoaderGGUF': {
                'input': {'required': {'unet_name': [[
                    'Qwen/qwen-image-2512-Q4_K_S.gguf',
                ]]}}
            },
            'LoraLoaderModelOnly': {
                'input': {'required': {'lora_name': [[
                    'Qwen/Qwen-Image-2512-Lightning-4steps-V1.0-bf16.safetensors',
                ]]}}
            },
        }

        def response_for(url, timeout):
            class_type = url.rsplit('/', 1)[-1]
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {class_type: schemas[class_type]}
            return response

        get.side_effect = response_for
        workflow = {
            '133': {'class_type': 'UnetLoaderGGUF', 'inputs': {
                'unet_name': 'Qwen\\qwen-image-2512-Q4_K_S.gguf',
            }},
            '134': {'class_type': 'LoraLoaderModelOnly', 'inputs': {
                'model': ['133', 0],
                'lora_name': 'Qwen\\Qwen-Image-2512-Lightning-4steps-V1.0-bf16.safetensors',
            }},
        }
        resolved = factory.comfy_resolve_workflow_options(workflow)
        self.assertEqual(len(resolved), 2)
        self.assertEqual(workflow['133']['inputs']['unet_name'],
                         'Qwen/qwen-image-2512-Q4_K_S.gguf')
        self.assertEqual(workflow['134']['inputs']['lora_name'],
                         'Qwen/Qwen-Image-2512-Lightning-4steps-V1.0-bf16.safetensors')
        self.assertEqual(workflow['134']['inputs']['model'], ['133', 0])

    @patch.object(factory.requests, 'get')
    def test_comfy_workflow_options_do_not_guess_unmatched_models(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'UnetLoaderGGUF': {
            'input': {'required': {'unet_name': [['Qwen/another-model.gguf']]}}
        }}
        get.return_value = response
        workflow = {'1': {'class_type': 'UnetLoaderGGUF', 'inputs': {
            'unet_name': 'Qwen\\missing-model.gguf',
            'free_text': 'folder\\prompt text',
        }}}
        resolved = factory.comfy_resolve_workflow_options(workflow)
        self.assertEqual(resolved, [])
        self.assertEqual(workflow['1']['inputs']['unet_name'], 'Qwen\\missing-model.gguf')
        self.assertEqual(workflow['1']['inputs']['free_text'], 'folder\\prompt text')

    @patch.object(factory.requests, 'get')
    def test_comfy_workflow_options_resolve_linux_paths_on_windows(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'VAELoader': {
            'input': {'required': {'vae_name': [['Qwen\\qwen_image_vae.safetensors']]}}
        }}
        get.return_value = response
        workflow = {'1': {'class_type': 'VAELoader', 'inputs': {
            'vae_name': 'Qwen/qwen_image_vae.safetensors',
        }}}
        resolved = factory.comfy_resolve_workflow_options(workflow)
        self.assertEqual(len(resolved), 1)
        self.assertEqual(workflow['1']['inputs']['vae_name'],
                         'Qwen\\qwen_image_vae.safetensors')

    @patch.object(factory.time, 'sleep', return_value=None)
    @patch.object(factory.requests, 'get')
    def test_waits_for_failed_prompt_to_leave_queue_before_freeing(self, get, _sleep):
        running = Mock()
        running.raise_for_status.return_value = None
        running.json.return_value = {'queue_running': [[1, 'prompt-123']], 'queue_pending': []}
        empty = Mock()
        empty.raise_for_status.return_value = None
        empty.json.return_value = {'queue_running': [], 'queue_pending': []}
        get.side_effect = [running, empty]
        exited, error = factory.comfy_wait_prompt_exit('prompt-123', timeout=2, interval=0)
        self.assertTrue(exited)
        self.assertIsNone(error)
        self.assertEqual(get.call_count, 2)

    def test_queue_prompt_ids_handles_comfy_list_and_dict_shapes(self):
        data = {
            'queue_running': [[1, 'alpha', {}, {}]],
            'queue_pending': [{'prompt_id': 'beta'}],
        }
        self.assertEqual(factory._comfy_queue_prompt_ids(data), {'alpha', 'beta'})

    @patch.dict(os.environ, {'AIX_COMFY_STOP_COMMAND': 'host-stop-comfy'}, clear=False)
    @patch.object(factory, 'run_runtime_env_command', return_value=(True, None))
    @patch.object(factory, 'wait_http_offline', return_value=True)
    def test_linux_managed_stop_uses_trusted_host_command(self, _offline, command):
        factory.CONFIG['comfyui_runtime_mode'] = 'managed'
        ok, message = factory.stop_comfyui()
        self.assertTrue(ok)
        self.assertIsNone(message)
        command.assert_called_once_with('AIX_COMFY_STOP_COMMAND')


if __name__ == '__main__':
    unittest.main()
