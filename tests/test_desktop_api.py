# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import app as factory


class DesktopApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_projects_dir = factory.PROJECTS_DIR
        factory.PROJECTS_DIR = self.temp_dir.name
        self.client = factory.app.test_client()

    def tearDown(self):
        factory.PROJECTS_DIR = self.old_projects_dir
        self.temp_dir.cleanup()

    def test_capabilities_are_versioned_and_safe(self):
        response = self.client.get('/api/desktop/v1/capabilities')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['api_version'], '1.0')
        self.assertTrue(data['features']['project_create_draft'])
        self.assertFalse(data['features']['production_start'])

    def test_desktop_safe_mode_blocks_legacy_production_routes(self):
        with patch.dict(os.environ, {'AIX_DESKTOP_MODE': '1'}):
            capabilities = self.client.get('/api/desktop/v1/capabilities')
            self.assertEqual(capabilities.status_code, 200)
            self.assertTrue(capabilities.get_json()['safe_mode'])

            blocked = self.client.get('/api/pipeline/run')
            self.assertEqual(blocked.status_code, 403)
            self.assertEqual(blocked.get_json()['msg'], '桌面安全模式未开放此操作')

            allowed = self.client.get('/api/desktop/v1/projects')
            self.assertEqual(allowed.status_code, 200)

    def test_create_list_and_read_draft_without_starting_pipeline(self):
        response = self.client.post('/api/desktop/v1/projects', json={
            'name': '桌面 Alpha 测试',
            'input_mode': 'story',
            'style': '电影写实',
        })
        self.assertEqual(response.status_code, 201)
        created = response.get_json()['project']
        pid = created['summary']['id']
        self.assertEqual(created['summary']['title'], '桌面 Alpha 测试')
        self.assertEqual(created['summary']['stage'], 'input')
        self.assertEqual(created['shots'], [])
        self.assertFalse(created['summary']['has_final'])

        listing = self.client.get('/api/desktop/v1/projects').get_json()
        self.assertEqual([item['id'] for item in listing['projects']], [pid])

        detail = self.client.get(f'/api/desktop/v1/projects/{pid}')
        self.assertEqual(detail.status_code, 200)
        project = detail.get_json()['project']
        self.assertEqual(project['summary']['id'], pid)
        self.assertNotIn('path', str(project))

    def test_invalid_project_id_is_rejected(self):
        response = self.client.get('/api/desktop/v1/projects/not%20valid')
        self.assertEqual(response.status_code, 400)

    def test_create_rejects_non_json_and_invalid_json(self):
        response = self.client.post('/api/desktop/v1/projects', data='plain text')
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            '/api/desktop/v1/projects',
            data='{broken',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_summary_prefers_final_and_clamps_progress(self):
        project = {
            'id': 'finished',
            'title': '已完成',
            'created': 1,
            'script': {'shots': [{'id': 1}]},
            'shots': [{'index': 1}, {'index': 2}],
            'assets': {},
            'preproduction': {'step': 'production'},
            'final': '/file/final.mp4',
        }
        summary = factory.desktop_project_summary(project)
        self.assertEqual(summary['stage'], 'complete')
        self.assertEqual(summary['progress'], 100)

        project['final'] = None
        summary = factory.desktop_project_summary(project)
        self.assertEqual(summary['progress'], 100)

    def test_patch_updates_draft_but_rejects_production_content_changes(self):
        created = self.client.post('/api/desktop/v1/projects', json={
            'name': '可编辑草稿',
            'input_mode': 'story',
        }).get_json()['project']
        pid = created['summary']['id']

        response = self.client.patch(f'/api/desktop/v1/projects/{pid}', json={
            'name': '新标题',
            'content': '一个雨夜故事',
            'style': '3D 动漫',
            'aspect_ratio': '16:9',
        })
        self.assertEqual(response.status_code, 200)
        updated = response.get_json()['project']
        self.assertEqual(updated['summary']['title'], '新标题')
        self.assertEqual(updated['idea'], '一个雨夜故事')
        self.assertEqual(updated['style'], '3D 动漫')
        self.assertEqual(updated['aspect_ratio'], '16:9 (Widescreen)')

        raw = factory.load_project(pid)
        raw['script'] = {'shots': []}
        factory.save_project(raw)
        response = self.client.patch(f'/api/desktop/v1/projects/{pid}', json={'content': '改写'})
        self.assertEqual(response.status_code, 409)

    def test_detail_read_does_not_mutate_saved_preproduction(self):
        project = {
            'id': 'legacy-project',
            'title': '旧项目',
            'created': 1,
            'script': {'shots': []},
            'shots': [],
            'assets': {},
            'final': None,
            'preproduction': {'step': 'character_review', 'asset_plan': []},
        }
        factory.save_project(project)
        response = self.client.get('/api/desktop/v1/projects/legacy-project')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['project']['preproduction']['step'], 'prompts')
        self.assertEqual(factory.load_project('legacy-project')['preproduction']['step'], 'character_review')

    @patch.object(factory, 'acceleration_status', return_value={'mode': 'test'})
    @patch.object(factory, 'find_ffmpeg', return_value='ffmpeg.exe')
    @patch.object(factory, 'comfy_check', return_value=True)
    @patch.object(factory.requests, 'get')
    def test_status_reports_requested_backend_port(self, mock_get, _comfy, _ffmpeg, _acceleration):
        mock_get.return_value.status_code = 200
        response = self.client.get('/api/desktop/v1/status', base_url='http://localhost:7999')
        self.assertEqual(response.status_code, 200)
        status = response.get_json()
        self.assertEqual(status['services']['backend']['port'], 7999)
        self.assertTrue(status['services']['llm']['online'])


if __name__ == '__main__':
    unittest.main()
