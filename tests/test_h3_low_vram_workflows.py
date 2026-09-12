# -*- coding: utf-8 -*-
import json
import os
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = ('h3_t2v.json', 'h3_i2v.json', 'h3_r2v.json')


class H3LowVramWorkflowTests(unittest.TestCase):
    def test_all_h3_workflows_use_low_vram_chain_without_te_speed(self):
        for filename in WORKFLOWS:
            with self.subTest(workflow=filename):
                path = os.path.join(ROOT, 'workflows', filename)
                with open(path, 'r', encoding='utf-8') as handle:
                    workflow = json.load(handle)

                classes = {node.get('class_type') for node in workflow.values()}
                self.assertNotIn('TESpeedMiniMaxH3', classes)
                self.assertEqual(
                    workflow['accel:lowvram']['class_type'],
                    'MiniMaxLowVRAMAttention',
                )
                self.assertEqual(
                    workflow['accel:ffn']['class_type'],
                    'MiniMaxChunkFeedForward',
                )
                self.assertEqual(
                    workflow['accel:lowvram']['inputs']['model'],
                    ['accel:sage', 0],
                )
                self.assertEqual(
                    workflow['accel:ffn']['inputs']['model'],
                    ['accel:lowvram', 0],
                )

                downstream = [
                    node['inputs']['model']
                    for node in workflow.values()
                    if node.get('class_type') in ('BasicScheduler', 'BasicGuider')
                ]
                self.assertTrue(downstream)
                self.assertTrue(all(model == ['accel:ffn', 0] for model in downstream))

    def test_failed_segment_without_saved_refs_resumes_pipeline(self):
        with open(os.path.join(ROOT, 'index.html'), 'r', encoding='utf-8') as handle:
            page = handle.read()
        self.assertIn('尚未成功保存，正在从该项目断点续跑', page)
        self.assertIn('runPipeline(currentPid);', page)
        self.assertNotIn('该镜头还没有生成记录，请先运行一遍流水线', page)


if __name__ == '__main__':
    unittest.main()
