# -*- coding: utf-8 -*-
import copy
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import app as factory


def response(status=200, payload=None):
    result = Mock()
    result.status_code = status
    result.ok = 200 <= status < 300
    result.json.return_value = payload or {}
    if result.ok:
        result.raise_for_status.return_value = None
    else:
        result.raise_for_status.side_effect = RuntimeError(f'HTTP {status}')
    return result


class PipelineStopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.original_projects = factory.PROJECTS_DIR
        factory.PROJECTS_DIR = self.temp.name
        self.release_project_jobs()
        self.client = factory.app.test_client()

    def tearDown(self):
        self.release_project_jobs()
        factory.PROJECTS_DIR = self.original_projects
        self.temp.cleanup()

    def release_project_jobs(self):
        for pid, (job_id, _handle) in list(factory._PROJECT_JOB_HANDLES.items()):
            factory.release_project_job(pid, job_id)

    def save_active(self, pid='project-1', prompt_id='owned-prompt', status='running'):
        project = {
            'id': pid, 'idea': 'test', 'assets': {'done': {'path': 'saved.png'}},
            'shots': [{'index': 1, 'video_url': '/saved.mp4'}], 'final': None,
            'production_job': {
                'run_id': 'run-1', 'status': status, 'stop_requested': False,
                'current_prompt_id': prompt_id, 'updated': time.time(),
            },
        }
        factory.save_project(project)
        return project

    def save_preproduction(self, pid='prep-1', outline_confirmed=False,
                           script_confirmed=False, script=None, prompts=None):
        project = {
            'id': pid, 'idea': '测试故事', 'input_mode': 'story', 'title': '测试项目',
            'style': '电影写实', 'assets': {}, 'shots': [], 'final': None,
            'script': script, 'prompts': prompts or {}, 'created': time.time(),
            'preproduction': {
                'version': 2, 'step': 'prompts' if script_confirmed else 'outline',
                'story_confirmed': True, 'outline': '已保存的大纲',
                'outline_confirmed': outline_confirmed,
                'script_confirmed': script_confirmed,
                'prompts_confirmed': False, 'asset_plan': [],
                'assets_confirmed': False,
                'asset_batch': {'status': 'waiting', 'total': 0, 'completed': 0, 'failed': 0},
                'updated': time.time(),
            },
        }
        factory.save_project(project)
        return project

    def stop_current_preproduction_job(self, pid):
        job = factory.load_project(pid)['production_job']
        response = factory.app.test_client().post(
            f'/api/project/{pid}/stop', json={'run_id': job['run_id']})
        self.assertEqual(response.status_code, 202)
        return job['run_id']

    @patch.object(factory.requests, 'get')
    @patch.object(factory.requests, 'post')
    def test_pending_stop_deletes_only_owned_prompt(self, post, get):
        self.save_active()
        post.side_effect = [response(404), response(200)]
        get.side_effect = [
            response(payload={'queue_running': [[1, 'foreign-running']],
                              'queue_pending': [[2, 'owned-prompt'], [3, 'foreign-pending']]}),
            response(payload={'queue_running': [[1, 'foreign-running']],
                              'queue_pending': [[3, 'foreign-pending']]}),
        ]

        result = self.client.post('/api/project/project-1/stop', json={'run_id': 'run-1'})

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.get_json()['action'], 'cancelled')
        queue_call = next(call for call in post.call_args_list if call.args[0].endswith('/queue'))
        self.assertEqual(queue_call.kwargs['json'], {'delete': ['owned-prompt']})
        self.assertFalse(any(call.args[0].endswith('/interrupt') for call in post.call_args_list))
        saved = factory.load_project('project-1')
        self.assertIn('done', saved['assets'])
        self.assertEqual(saved['shots'][0]['video_url'], '/saved.mp4')

    @patch.object(factory.requests, 'get')
    @patch.object(factory.requests, 'post')
    def test_legacy_running_prompt_is_deferred_without_global_interrupt(self, post, get):
        self.save_active()
        post.return_value = response(404)
        get.return_value = response(payload={
            'queue_running': [[1, 'owned-prompt'], [2, 'foreign-running']],
            'queue_pending': [],
        })

        result = self.client.post('/api/project/project-1/stop', json={'run_id': 'run-1'})

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.get_json()['action'], 'deferred')
        self.assertFalse(any(call.args[0].endswith('/interrupt') for call in post.call_args_list))
        self.assertEqual(factory.load_project('project-1')['production_job']['status'], 'stopping')

    @patch.object(factory.requests, 'post')
    def test_atomic_job_cancel_targets_only_owned_prompt(self, post):
        self.save_active()
        post.return_value = response(payload={'cancelled': True})

        result = self.client.post('/api/project/project-1/stop', json={'run_id': 'run-1'})

        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.get_json()['action'], 'cancelled')
        self.assertEqual(len(post.call_args_list), 1)
        self.assertTrue(post.call_args.args[0].endswith('/api/jobs/owned-prompt/cancel'))

    @patch.object(factory.requests, 'post')
    def test_repeated_stop_is_idempotent(self, post):
        self.save_active(prompt_id=None)

        first = self.client.post('/api/project/project-1/stop', json={'run_id': 'run-1'})
        second = self.client.post('/api/project/project-1/stop', json={'run_id': 'run-1'})

        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.get_json()['changed'])
        post.assert_not_called()

    @patch.object(factory.requests, 'post')
    def test_completed_job_stop_is_noop(self, post):
        project = self.save_active(status='done')
        project['final'] = '/file/outputs/project-1/final.mp4'
        factory.save_project(project)

        result = self.client.post('/api/project/project-1/stop', json={'run_id': 'run-1'})

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()['status'], 'done')
        self.assertFalse(result.get_json()['changed'])
        post.assert_not_called()

    def test_stale_page_cannot_stop_a_new_run(self):
        self.save_active()
        result = self.client.post('/api/project/project-1/stop', json={'run_id': 'old-run'})
        self.assertEqual(result.status_code, 409)
        self.assertFalse(factory.load_project('project-1')['production_job']['stop_requested'])

    @patch.object(factory.requests, 'post')
    def test_terminal_state_compare_and_set_is_not_overwritten(self, post):
        project = self.save_active(status='done')
        project['production_job']['updated'] = time.time() + 1
        factory.save_project(project)

        result = self.client.post('/api/project/project-1/stop', json={'run_id': 'run-1'})

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.get_json()['status'], 'done')
        self.assertEqual(factory.load_project('project-1')['production_job']['status'], 'done')
        post.assert_not_called()

    @patch.object(factory.time, 'sleep', return_value=None)
    @patch.object(factory.time, 'monotonic', side_effect=[10, 10, 14])
    @patch.object(factory, 'comfy_wait_prompt_exit', return_value=(False, 'still running'))
    @patch.object(factory.requests, 'get')
    def test_cancelled_prompt_converges_after_it_leaves_queue(self, get, _exit, _mono, _sleep):
        get.side_effect = [
            response(payload={}), response(payload={'queue_running': [], 'queue_pending': []}),
            response(payload={}), response(payload={'queue_running': [], 'queue_pending': []}),
        ]

        history, error = factory.comfy_wait(
            'owned-prompt', timeout=30, interval=0,
            stop_check=lambda: True,
            stop_handler=lambda _prompt_id: ('cancelled', 'cancel accepted'))

        self.assertIsNone(history)
        self.assertIn('__AIX_STOPPED__', error)
        self.assertLessEqual(get.call_count, 4)

    @patch.object(factory.time, 'monotonic', return_value=10)
    @patch.object(factory, 'comfy_wait_prompt_exit', return_value=(True, None))
    @patch.object(factory.requests, 'get')
    def test_cancel_race_preserves_already_completed_history(self, get, _exit, _mono):
        completed = {'status': {'completed': True}, 'outputs': {'1': {'images': [{'filename': 'done.png'}]}}}
        get.return_value = response(payload={'owned-prompt': completed})

        history, error = factory.comfy_wait(
            'owned-prompt', timeout=30, interval=0,
            stop_check=lambda: True,
            stop_handler=lambda _prompt_id: ('cancelled', 'cancel accepted'))

        self.assertIsNone(error)
        self.assertEqual(history, completed)

    @patch.object(factory, 'comfy_submit', side_effect=RuntimeError('submit failed'))
    @patch.object(factory, 'comfy_open_ws')
    @patch.object(factory, 'comfy_missing_node_types', return_value=[])
    @patch.object(factory, 'load_t2i_workflow')
    def test_submit_failure_closes_image_progress_socket(self, workflow, _missing, open_ws, _submit):
        workflow.return_value = {
            'json': {
                '1': {'inputs': {'text': ''}}, '2': {'inputs': {'seed': 0}},
                '3': {'inputs': {'width': 0}}, '4': {'inputs': {'height': 0}},
            },
            'map': {'prompt': ['1', 'text'], 'seed': ['2', 'seed'],
                    'width': ['3', 'width'], 'height': ['4', 'height']},
        }
        socket = Mock()
        open_ws.return_value = socket

        with self.assertRaisesRegex(RuntimeError, 'submit failed'):
            factory.gen_image('test')

        socket.close.assert_called_once()

    def test_stale_save_preserves_newer_stop_state(self):
        stale = self.save_active(prompt_id=None)
        factory.update_production_job('project-1', 'run-1', status='stopping', stop_requested=True)
        stale['title'] = 'late progress save'
        factory.save_project(stale)
        job = factory.load_project('project-1')['production_job']
        self.assertEqual(job['status'], 'stopping')
        self.assertTrue(job['stop_requested'])

    def test_equal_timestamp_terminal_status_replaces_nonterminal_status(self):
        project = self.save_active(prompt_id=None, status='merging')
        project['production_job']['updated'] = 100
        factory.save_project(project, preserve_runtime=False)
        finished = copy.deepcopy(project)
        finished['production_job'].update({'status': 'failed', 'updated': 100})

        factory.save_project(finished)

        self.assertEqual(factory.load_project('project-1')['production_job']['status'], 'failed')

    def test_equal_timestamp_active_snapshot_cannot_replace_terminal_status(self):
        project = self.save_active(prompt_id=None, status='failed')
        project['production_job']['updated'] = 100
        factory.save_project(project, preserve_runtime=False)
        stale = copy.deepcopy(project)
        stale['production_job'].update({'status': 'running', 'updated': 100})

        factory.save_project(stale)

        self.assertEqual(factory.load_project('project-1')['production_job']['status'], 'failed')

    def test_finalize_stop_preserves_completed_items(self):
        project = self.save_active(prompt_id=None)
        project['item_states'] = {'shots': {
            '1': {'status': 'done', 'message': 'saved'},
            '2': {'status': 'generating', 'message': 'working'},
        }}
        factory.save_project(project)
        factory.finalize_project_stopped('project-1', 'run-1', 'stopped safely')
        saved = factory.load_project('project-1')
        self.assertEqual(saved['item_states']['shots']['1']['status'], 'done')
        self.assertEqual(saved['item_states']['shots']['2']['status'], 'waiting')
        self.assertEqual(saved['production_job']['status'], 'stopped')
        self.assertEqual(saved['shots'][0]['video_url'], '/saved.mp4')

    def test_retry_job_honors_stop_before_starting_generation(self):
        project = self.save_active(prompt_id=None, status='retrying')
        project['shots'] = []
        project['script'] = {'shots': [{
            'index': 1, 'segment_id': 'EP01-01', 'duration': 8,
            'characters': [], 'props': [], 'scene': '', 'action': 'test',
        }]}
        project['prompts'] = {'1': 'saved prompt'}
        project['item_states'] = {'shots': {'1': {
            'status': 'retrying', 'retry_count': 1, 'message': 'retry queued',
        }}}
        factory.save_project(project)
        self.assertTrue(factory.claim_project_job('project-1', 'run-1'))

        response = self.client.post('/api/project/project-1/stop', json={'run_id': 'run-1'})
        factory.run_project_shot_retry('project-1', 1, 'run-1')

        self.assertEqual(response.status_code, 202)
        saved = factory.load_project('project-1')
        self.assertEqual(saved['production_job']['status'], 'stopped')
        self.assertEqual(saved['item_states']['shots']['1']['status'], 'waiting')
        self.assertFalse(factory.project_job_active('project-1'))

    def test_recovery_converges_orphaned_stopping_job_to_stopped(self):
        project = self.save_active(prompt_id=None, status='stopping')
        project['production_job']['stop_requested'] = True
        factory.save_project(project)

        response = self.client.get('/api/project/project-1')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['project']['production_job']['status'], 'stopped')
        self.assertEqual(factory.load_project('project-1')['production_job']['status'], 'stopped')

    def test_recovery_holds_project_lock_until_state_is_saved(self):
        project = self.save_active(prompt_id=None, status='running')
        original_save = factory.save_project
        competing_claims = []

        def save_while_competing(current, preserve_runtime=True):
            competing_claims.append(factory.claim_project_job('project-1', 'new-run'))
            original_save(current, preserve_runtime=preserve_runtime)

        with patch.object(factory, 'save_project', side_effect=save_while_competing):
            changed = factory.recover_interrupted_shot_retries(project)

        self.assertTrue(changed)
        self.assertEqual(competing_claims, [False])
        self.assertFalse(factory.project_job_active('project-1'))

    def test_idle_project_poll_does_not_claim_production_lock(self):
        project = self.save_active(prompt_id=None, status='failed')

        with patch.object(factory, 'claim_project_job', wraps=factory.claim_project_job) as claim:
            changed = factory.recover_interrupted_shot_retries(project)

        self.assertFalse(changed)
        claim.assert_not_called()
        self.assertFalse(factory.project_job_active('project-1'))

    def test_duplicate_begin_is_rejected(self):
        project = self.save_active(prompt_id=None, status='stopped')
        project['production_job']['updated'] = 0
        factory.save_project(project)
        run_id = factory.begin_production_job('project-1', 'pipeline')
        try:
            with self.assertRaises(factory.ProjectAlreadyRunning):
                factory.begin_production_job('project-1', 'pipeline')
        finally:
            factory.end_production_job('project-1', run_id)

    @patch.object(factory, 'prepare_llm_stage', return_value=(True, None))
    @patch.object(factory, 'llm_chat')
    def test_outline_stop_survives_refresh_and_allows_regeneration(self, llm_chat, _prepare):
        self.save_preproduction()
        observed = {}

        def stop_during_outline(*_args, **_kwargs):
            observed['first_run_id'] = self.stop_current_preproduction_job('prep-1')
            refreshed = factory.app.test_client().get('/api/project/prep-1').get_json()['project']
            observed['refresh_status'] = refreshed['production_job']['status']
            return '不应保存的新大纲', None

        llm_chat.side_effect = stop_during_outline
        stopped = self.client.post('/api/preproduction/prep-1/outline/generate')

        self.assertEqual(stopped.status_code, 200)
        self.assertTrue(stopped.get_json()['stopped'])
        self.assertEqual(observed['refresh_status'], 'stopping')
        saved = factory.load_project('prep-1')
        self.assertEqual(saved['production_job']['status'], 'stopped')
        self.assertEqual(saved['preproduction']['outline'], '已保存的大纲')
        self.assertFalse(factory.project_job_active('prep-1'))

        llm_chat.side_effect = None
        llm_chat.return_value = ('重新生成成功的大纲', None)
        regenerated = self.client.post('/api/preproduction/prep-1/outline/generate')

        self.assertEqual(regenerated.status_code, 200)
        self.assertFalse(regenerated.get_json().get('stopped', False))
        saved = factory.load_project('prep-1')
        self.assertEqual(saved['production_job']['status'], 'done')
        self.assertNotEqual(saved['production_job']['run_id'], observed['first_run_id'])
        self.assertEqual(saved['preproduction']['outline'], '重新生成成功的大纲')

    @patch.object(factory, 'prepare_llm_stage', return_value=(True, None))
    @patch.object(factory, 'llm_chat')
    def test_script_generation_can_be_stopped_without_replacing_saved_script(self, llm_chat, _prepare):
        old_script = {'title': '旧剧本', 'shots': [{'index': 1, 'action': '旧动作'}]}
        self.save_preproduction(outline_confirmed=True, script=old_script)
        generated = {
            'title': '新剧本',
            'characters': [], 'scenes': [], 'props': [],
            'shots': [{'index': 1, 'duration': 8, 'action': '新动作', 'camera': '近景'}],
        }

        def stop_during_script(*_args, **_kwargs):
            self.stop_current_preproduction_job('prep-1')
            return json.dumps(generated, ensure_ascii=False), None

        llm_chat.side_effect = stop_during_script
        response = self.client.post('/api/preproduction/prep-1/script/generate')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['stopped'])
        saved = factory.load_project('prep-1')
        self.assertEqual(saved['production_job']['status'], 'stopped')
        self.assertEqual(saved['script'], old_script)

    @patch.object(factory, 'prepare_llm_stage', return_value=(True, None))
    @patch.object(factory, 'gen_shot_h3_prompt')
    def test_prompt_batch_stop_preserves_only_completed_prompts(self, generate_prompt, _prepare):
        script = {
            'title': '两片短剧', 'characters': [], 'scenes': [], 'props': [],
            'shots': [
                {'index': 1, 'segment_id': 'EP01-01', 'duration': 8,
                 'characters': [], 'props': [], 'scene': '', 'action': '动作一', 'camera': '近景'},
                {'index': 2, 'segment_id': 'EP01-02', 'duration': 8,
                 'characters': [], 'props': [], 'scene': '', 'action': '动作二', 'camera': '远景'},
            ],
        }
        self.save_preproduction(
            outline_confirmed=True, script_confirmed=True, script=script)

        def generate_then_stop(shot, *_args, **_kwargs):
            if shot['index'] == 1:
                return '已完成的第一片提示词', None
            self.stop_current_preproduction_job('prep-1')
            return '停止后返回的第二片提示词', None

        generate_prompt.side_effect = generate_then_stop
        response = self.client.post('/api/preproduction/prep-1/prompts/generate')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()['stopped'])
        saved = factory.load_project('prep-1')
        self.assertEqual(saved['production_job']['status'], 'stopped')
        self.assertEqual(saved['prompts'], {'1': '已完成的第一片提示词'})
        self.assertEqual(saved['preproduction']['step'], 'prompts')

    @patch.object(factory.time, 'sleep')
    @patch.object(factory, 'ensure_local_llm')
    @patch.object(factory, 'get_llm_endpoint', return_value=('http://llm.test', 'EMPTY', 'test-model'))
    @patch.object(factory.requests, 'post')
    def test_llm_stop_after_failed_request_prevents_recovery_and_retry(
            self, post, _endpoint, recover, sleep):
        stopped = {'value': False}

        def fail_once(*_args, **_kwargs):
            stopped['value'] = True
            raise factory.requests.exceptions.ConnectionError('offline')

        post.side_effect = fail_once
        with self.assertRaises(factory.ProjectStopRequested):
            factory.llm_chat(
                [{'role': 'user', 'content': 'test'}], retries=3,
                stop_check=lambda: stopped['value'])

        self.assertEqual(post.call_count, 1)
        recover.assert_not_called()
        sleep.assert_not_called()

    @patch.object(factory, 'llm_chat')
    def test_prompt_stop_after_first_draft_skips_repair_request(self, llm_chat):
        stopped = {'value': False}
        shot = {
            'index': 1, 'segment_id': 'EP01-01', 'duration': 8,
            'characters': [], 'props': [], 'scene': '',
            'action': '测试动作', 'camera': '近景',
        }

        def return_draft(*_args, **_kwargs):
            stopped['value'] = True
            return '需要修复的首稿', None

        llm_chat.side_effect = return_draft
        with self.assertRaises(factory.ProjectStopRequested):
            factory.gen_shot_h3_prompt(
                shot, stop_check=lambda: stopped['value'])

        self.assertEqual(llm_chat.call_count, 1)


if __name__ == '__main__':
    unittest.main()
