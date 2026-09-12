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


class ShotRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_projects_dir = factory.PROJECTS_DIR
        self.old_outputs_dir = factory.OUTPUTS_DIR
        factory.PROJECTS_DIR = self.temp_dir.name
        factory.OUTPUTS_DIR = os.path.join(self.temp_dir.name, 'outputs')
        os.makedirs(factory.OUTPUTS_DIR, exist_ok=True)
        self.release_project_jobs()
        self.client = factory.app.test_client()

    def tearDown(self):
        self.release_project_jobs()
        factory.PROJECTS_DIR = self.old_projects_dir
        factory.OUTPUTS_DIR = self.old_outputs_dir
        self.temp_dir.cleanup()

    def release_project_jobs(self):
        for pid, (job_id, _handle) in list(factory._PROJECT_JOB_HANDLES.items()):
            factory.release_project_job(pid, job_id)

    def save_failed_project(self, pid='retry-project', shot_count=1):
        shots = [
            {
                'index': index, 'segment_id': f'EP01-{index:02d}',
                'duration': 8, 'characters': [], 'props': [],
                'scene': '', 'action': f'片段{index}', 'dialogue': [],
            }
            for index in range(1, shot_count + 1)
        ]
        project = {
            'id': pid, 'idea': '测试故事', 'input_mode': 'story', 'title': '重试测试',
            'script': {'title': '重试测试', 'characters': [], 'scenes': [], 'props': [], 'shots': shots},
            'assets': {}, 'shots': [], 'prompts': {str(index): f'提示词{index}' for index in range(1, shot_count + 1)},
            'item_states': {'shots': {
                '1': {'status': 'failed', 'progress': 0, 'message': '首次生成失败', 'error': '首次生成失败'},
            }},
            'final': None, 'created': 1,
        }
        factory.save_project(project)
        return project

    @patch.object(factory.threading, 'Thread')
    def test_retry_api_queues_failed_segment_and_rejects_duplicate(self, thread_cls):
        self.save_failed_project()

        response = self.client.post('/api/project/retry-project/shot/1/retry')
        self.assertEqual(response.status_code, 202)
        data = response.get_json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['item_state']['status'], 'retrying')
        self.assertEqual(data['item_state']['retry_count'], 1)
        thread_cls.return_value.start.assert_called_once_with()

        saved = factory.load_project('retry-project')
        state = saved['item_states']['shots']['1']
        self.assertEqual(state['original_error'], '首次生成失败')
        self.assertEqual(state['retry_count'], 1)

        duplicate = self.client.post('/api/project/retry-project/shot/1/retry')
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn('已有生成任务', duplicate.get_json()['msg'])

    @patch.object(factory.threading, 'Thread')
    def test_project_lock_rejects_a_different_segment_retry(self, _thread_cls):
        project = self.save_failed_project(shot_count=2)
        project['item_states']['shots']['2'] = {
            'status': 'failed', 'progress': 0, 'message': '第二片失败', 'error': '第二片失败',
        }
        factory.save_project(project)

        first = self.client.post('/api/project/retry-project/shot/1/retry')
        second = self.client.post('/api/project/retry-project/shot/2/retry')

        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 409)
        self.assertIn('已有生成任务', second.get_json()['msg'])

    @patch.object(factory, 'save_config')
    def test_project_lock_rejects_full_pipeline_while_retry_is_active(self, _save_config):
        self.save_failed_project()
        self.assertTrue(factory.claim_project_job('retry-project', 'active-retry'))

        response = self.client.get('/api/pipeline/run?pid=retry-project&idea=测试故事')
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('event: pipeline_error', body)
        self.assertIn('已有生成任务', body)

    @patch.object(factory, 'find_ffmpeg')
    @patch.object(factory, 'comfy_download')
    @patch.object(factory, 'gen_video_r2v', return_value=({'filename': 'video.mp4'}, None))
    @patch.object(factory, 'assemble_shot_refs', return_value=(['ref.png'], None, None))
    @patch.object(factory, 'prepare_comfy_stage', return_value=True)
    def test_retry_pipeline_generates_only_selected_segment(
            self, _prepare, _refs, generate, _download, ffmpeg):
        project = self.save_failed_project(shot_count=3)
        project['shots'] = [{
            'index': 1, 'segment_id': 'EP01-01', 'video_url': '/file/outputs/retry-project/shot_01.mp4',
            'prompt': '原提示词1', 'path': 'existing-shot-01.mp4', 'refs': ['old-ref.png'], 'duration': 8,
        }]
        project['item_states']['shots'] = {
            '1': {'status': 'done', 'progress': 100, 'message': '片段已完成'},
            '2': {'status': 'failed', 'progress': 0, 'message': '第二片失败', 'error': '第二片失败'},
            '3': {'status': 'waiting', 'progress': 0, 'message': '等待生成'},
        }
        factory.save_project(project)

        job_id = 'retry-job'
        self.assertTrue(factory.claim_project_job('retry-project', job_id))
        factory.run_project_shot_retry('retry-project', 2, job_id)

        saved = factory.load_project('retry-project')
        self.assertEqual(sorted(shot['index'] for shot in saved['shots']), [1, 2])
        self.assertEqual(next(shot for shot in saved['shots'] if shot['index'] == 1)['prompt'], '原提示词1')
        self.assertEqual(saved['item_states']['shots']['2']['status'], 'done')
        self.assertEqual(saved['item_states']['shots']['3']['status'], 'waiting')
        self.assertIsNone(saved.get('final'))
        generate.assert_called_once()
        ffmpeg.assert_not_called()
        self.assertEqual(saved['production_job']['status'], 'done')
        self.assertIn('仍有1个片段待生成', saved['production_job']['message'])

    def test_project_read_recovers_interrupted_retry(self):
        project = self.save_failed_project()
        project['item_states']['shots']['1'].update({'status': 'retrying', 'retry_count': 2})
        factory.save_project(project)

        self.assertTrue(factory.claim_project_job('retry-project', 'active-job'))
        active_response = self.client.get('/api/project/retry-project')
        self.assertEqual(active_response.get_json()['project']['item_states']['shots']['1']['status'], 'retrying')
        factory.release_project_job('retry-project', 'active-job')

        response = self.client.get('/api/project/retry-project')

        self.assertEqual(response.status_code, 200)
        state = response.get_json()['project']['item_states']['shots']['1']
        self.assertEqual(state['status'], 'failed')
        self.assertEqual(state['retry_count'], 2)
        self.assertIn('重试中断', state['message'])

    def test_project_read_recovers_interrupted_full_pipeline(self):
        project = self.save_failed_project()
        project['production_job'] = {'status': 'running', 'message': '正在生成短剧'}
        factory.save_project(project)

        response = self.client.get('/api/project/retry-project')

        self.assertEqual(response.status_code, 200)
        job = response.get_json()['project']['production_job']
        self.assertEqual(job['status'], 'failed')
        self.assertIn('生成任务中断', job['message'])

    def test_project_read_recovers_interrupted_final_merge(self):
        project = self.save_failed_project()
        project['shots'] = [{
            'index': 1, 'video_url': '/file/outputs/retry-project/shot_01.mp4',
            'path': 'outputs/retry-project/shot_01.mp4',
        }]
        project['item_states']['shots']['1']['status'] = 'done'
        project['production_job'] = {
            'status': 'merging', 'stage': 'finalizing', 'message': '正在合并所有片段',
        }
        factory.save_project(project)

        response = self.client.get('/api/project/retry-project')

        job = response.get_json()['project']['production_job']
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['stage'], 'finalizing')
        self.assertIn('视频合成中断', job['message'])

    @patch('builtins.open', side_effect=PermissionError('read only'))
    def test_project_lock_open_failure_is_reported_as_unavailable(self, _open):
        self.assertIsNone(factory._lock_project_job_file('retry-project'))

    @patch.object(factory.threading, 'Thread')
    def test_retry_post_recovers_stale_retry_without_prior_poll(self, _thread_cls):
        project = self.save_failed_project()
        project['item_states']['shots']['1'].update({'status': 'retrying', 'retry_count': 2})
        project['production_job'] = {'status': 'retrying', 'message': '正在重试'}
        factory.save_project(project)

        response = self.client.post('/api/project/retry-project/shot/1/retry')

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()['item_state']['retry_count'], 3)

    @patch.object(factory, 'find_ffmpeg', return_value=None)
    @patch.object(factory, 'comfy_download')
    @patch.object(factory, 'gen_video_r2v', return_value=({'filename': 'video.mp4'}, None))
    @patch.object(factory, 'assemble_shot_refs', return_value=(['ref.png'], None, None))
    @patch.object(factory, 'prepare_comfy_stage', return_value=True)
    def test_final_merge_failure_keeps_retried_segment_done(
            self, _prepare, _refs, _generate, _download, _ffmpeg):
        self.save_failed_project()
        job_id = 'merge-failure-job'
        self.assertTrue(factory.claim_project_job('retry-project', job_id))

        factory.run_project_shot_retry('retry-project', 1, job_id)

        saved = factory.load_project('retry-project')
        self.assertEqual(saved['item_states']['shots']['1']['status'], 'done')
        self.assertEqual(saved['production_job']['status'], 'failed')
        self.assertEqual(saved['production_job']['stage'], 'finalizing')
        self.assertIsNone(saved.get('final'))
        response = self.client.post('/api/project/retry-project/shot/1/retry')
        self.assertEqual(response.status_code, 409)
        self.assertIn('已经生成完成', response.get_json()['msg'])

    @patch.object(factory, 'set_item_state', side_effect=OSError('disk unavailable'))
    def test_retry_queue_save_failure_releases_project_lock(self, _set_state):
        self.save_failed_project()

        response = self.client.post('/api/project/retry-project/shot/1/retry')

        self.assertEqual(response.status_code, 500)
        self.assertFalse(factory.project_job_active('retry-project'))


if __name__ == '__main__':
    unittest.main()
