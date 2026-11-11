import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from am_seo.readability_scan import scan
from am_seo.geo_workspace import GeoWorkspace

URL = 'https://store.angrymiao.com/products/example'
HTML = '<html><body><h1>AM product</h1><p>' + 'Product information and supported use cases. ' * 3 + 'Price $149. Size 120 mm. USB compatibility.</p><h2>How to connect?</h2><p>Read the model-specific guide.</p></body></html>'


class ReadabilityScanTests(unittest.TestCase):
    def fetcher(self, html=HTML, md=None, llms=None):
        def fetch(url):
            if url.endswith('.md'): body, kind, status = (md, 'text/markdown', 200) if md is not None else ('<html>fallback</html>', 'text/html', 200)
            elif url.endswith('llms.txt'): body, kind, status = (llms, 'text/plain', 200) if llms is not None else ('missing', 'text/plain', 404)
            else: body, kind, status = html, 'text/html', 200
            return dict(url=url, final_url=url, status=status, body=body, content_type=kind, captured_at='2026-11-11T00:00:00Z')
        return fetch

    def test_missing_optional_files_do_not_fail_required_readability(self):
        report, captures = scan(self.fetcher(), URL)
        self.assertEqual(len(captures), 3)
        self.assertTrue(all(c['passed'] for c in report['checks'] if c['required']))
        optional = {c['id']:c for c in report['checks']}
        self.assertIsNone(optional['markdown']['passed'])
        self.assertIsNone(optional['llms']['passed'])
        self.assertNotIn('score', report)

    def test_script_json_and_hidden_numbers_are_not_visible_facts(self):
        html = HTML + '<script>{"price":"$999"}</script><p hidden>900 mm</p><p style="display: none">$888</p><template>999 mm</template>'
        report, _ = scan(self.fetcher(html), URL)
        facts = next(c for c in report['checks'] if c['id']=='fact_clues')['detail']
        self.assertIn('$149',facts)
        for token in ('$999','$888','900mm','999mm'): self.assertNotIn(token, facts)

    def test_javascript_only_shell_fails_required_text_check(self):
        report,_=scan(self.fetcher('<html><body><h1>AM</h1><script>'+HTML+'</script></body></html>'),URL)
        self.assertFalse(next(c for c in report['checks'] if c['id']=='visible_text')['passed'])

    def test_markdown_numeric_differences_require_review_not_a_lift_score(self):
        report,_=scan(self.fetcher(md='# AM product\nPrice $199. Dimensions 120 mm. Read the guide.'),URL)
        check=next(c for c in report['checks'] if c['id']=='markdown_consistency')
        self.assertIsNone(check['passed'])
        self.assertIn('$149',check['detail']);self.assertIn('$199',check['detail'])
        self.assertFalse(check['required'])

    def test_optional_network_failure_does_not_become_page_failure(self):
        base=self.fetcher()
        def fetch(url):
            if url.endswith('.md'):raise OSError('fixture unavailable')
            return base(url)
        report,_=scan(fetch,URL)
        self.assertTrue(all(c['passed'] for c in report['checks'] if c['required']))

    def test_http_error_page_fails_even_if_it_has_lots_of_text(self):
        base=self.fetcher()
        def fetch(url):
            result=base(url)
            if url==URL:result['status']=404
            return result
        report,_=scan(fetch,URL)
        self.assertFalse(next(c for c in report['checks'] if c['id']=='html')['passed'])

    def test_existing_workspace_gets_scan_once_preserves_evidence_and_checkbox(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'outputs/geo-workspace/state.json';state.parent.mkdir(parents=True)
            state.write_text(json.dumps({'tasks':[{'id':'existing','kind':'robots','status':'ready','execution_done':True,'verification':{'checked_at':'old'}}],'history':[],'traffic':None}))
            workspace=GeoWorkspace(root,fetcher=self.fetcher())
            self.assertTrue(workspace.task('existing')['execution_done'])
            self.assertEqual(workspace.task('existing')['verification']['checked_at'],'old')
            result=workspace.check('agent-readability')
            self.assertEqual(result['check_status'],'passed')
            self.assertNotIn('execution_done',result)
            self.assertEqual(len(result['verification']['evidence']),3)
            for evidence in result['verification']['evidence']:self.assertTrue((root/evidence['path']).is_file())
            restored=GeoWorkspace(root)
            self.assertEqual(sum(t['id']=='agent-readability' for t in restored.state()['tasks']),1)
            self.assertEqual(restored.state()['tasks'][-1]['group'],'foundation')
