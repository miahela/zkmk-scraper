import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from scraper import CompanyExtractor, ZKMKScraper


class ScraperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.categories = self.root / 'categories.csv'
        self.categories.write_text('categories,categories-href\nDemo,https://zk.mk/demo\n', encoding='utf-8')
        self.output = self.root / 'all.csv'
        self.priority = self.root / 'priority.csv'
        self.scraper = ZKMKScraper(str(self.categories), delay=(0, 0),
                                   output=str(self.output), priority_output=str(self.priority))
        self.addCleanup(self.scraper.session.close)

    def test_query_relative_pagination_and_cycle(self):
        html = '<div class="pagination"><a rel="next" href="?page=2">Next</a></div>'
        with patch.object(self.scraper, '_get', return_value=html) as get:
            self.scraper._scrape_category(self.scraper.categories.categories[0])
        self.assertEqual([c.args[0] for c in get.call_args_list],
                         ['https://zk.mk/demo', 'https://zk.mk/demo?page=2'])

    def test_page_limit(self):
        self.scraper.max_pages = 1
        with patch.object(self.scraper, '_get', return_value='<div class="pagination"><a rel="next" href="?page=2">Next</a></div>') as get:
            self.scraper._scrape_category(self.scraper.categories.categories[0])
        self.assertEqual(get.call_count, 1)

    def test_request_failure_is_visible(self):
        with patch.object(self.scraper.session, 'get', side_effect=requests.exceptions.Timeout('demo timeout')), \
                patch('scraper.time.sleep'), patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertIsNone(self.scraper._get('https://zk.mk/demo'))
        self.assertIn('Request failed after 3 attempts', output.getvalue())
        self.assertIn('Timeout', output.getvalue())

    def test_empty_page_reports_title(self):
        with patch.object(self.scraper, '_get', return_value='<html><title>Demo challenge</title></html>'), \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            self.scraper._scrape_category(self.scraper.categories.categories[0])
        self.assertIn('No listings parsed', output.getvalue())
        self.assertIn('Demo challenge', output.getvalue())

    def test_debug_saves_response(self):
        self.scraper.debug = True
        response = Mock(status_code=200, url='https://zk.mk/demo', content=b'<title>Demo</title>',
                        text='<title>Demo</title>')
        with patch.object(self.scraper.session, 'get', return_value=response), \
                patch('scraper.Path.write_text') as write, patch('scraper.time.sleep'), \
                patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(self.scraper._get(response.url), response.text)
        write.assert_called_once_with(response.text, encoding='utf-8')
        self.assertIn('HTTP 200', output.getvalue())

    def test_accept_encoding_uses_requests_defaults(self):
        # Requests advertises Brotli only when its decoder is installed.
        self.assertEqual(self.scraper.session.headers['Accept-Encoding'],
                         requests.utils.default_headers()['Accept-Encoding'])

    def test_empty_run_clears_both_old_outputs(self):
        for path in (self.output, self.priority):
            path.write_text('old records', encoding='utf-8')
        with patch.object(self.scraper, '_get', return_value=None):
            self.scraper.run('test')
        for path in (self.output, self.priority):
            with path.open(encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                self.assertIn('name', reader.fieldnames)
                self.assertEqual(list(reader), [])

    def test_invalid_configuration(self):
        for kwargs in ({'delay': (-1, 2)}, {'delay': (2, 1)}, {'max_pages': 0},
                       {'output': 'same.csv', 'priority_output': 'same.csv'},
                       {'output': str(self.categories)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ZKMKScraper(str(self.categories), **kwargs)

    def test_extracts_fake_listing(self):
        html = '''<div itemtype="http://schema.org/LocalBusiness" zkid="demo-001">
        <a class="companyname" href="/example"><span itemprop="name">Example Workshop</span></a>
        <span itemprop="telephone">DEMO-PHONE</span>
        <span itemprop="streetAddress">Example Street 1</span>
        <span itemprop="addressLocality">Demo City</span></div>'''
        companies = CompanyExtractor.from_html(html, 'Demo')
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies[0].name, 'Example Workshop')
        self.assertEqual(companies[0].phone, 'DEMO-PHONE')
        self.assertEqual(companies[0].company_url, '/example')


if __name__ == '__main__':
    unittest.main()
