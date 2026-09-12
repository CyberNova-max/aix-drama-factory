# -*- coding: utf-8 -*-
import copy
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
        with factory._ACTIVE_PRODUCTION_LOCK:
            factory._ACTIVE_PRODUCTION_RUNS.clear()
        self.client = factory.app.test_client()

    def tearDown(self):
        with factory._ACTIVE_PRODUCTION_LOCK:
            factory._ACTIVE_PRODUCTION_RUNS.clear()
        factory.PROJECTS_DIR = self.original_projects
        self.temp.cleanup()

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


if __name__ == '__main__':
    unittest.main()
