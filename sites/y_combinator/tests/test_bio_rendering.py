import json
import os
from pathlib import Path
import re
import sys

import pytest
from markupsafe import Markup

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))
os.environ["WEBSYN_SKIP_BOOTSTRAP"] = "1"

from app import app, safe_markdown_links


def test_http_markdown_link_renders_as_anchor():
    bio = 'She is the author of [Founders at Work](http://www.amazon.com/gp/product/1590597141) (2007).'
    rendered = safe_markdown_links(bio)
    assert isinstance(rendered, Markup)
    assert str(rendered) == 'She is the author of <a href="http://www.amazon.com/gp/product/1590597141">Founders at Work</a> (2007).'
    with app.app_context():
        assert app.jinja_env.from_string('{{ bio | safe_markdown_links }}').render(bio=bio) == str(rendered)


def test_all_current_rendered_markdown_link_fields_use_the_safe_renderer():
    source = json.loads((SITE / 'source_data.json').read_text())
    pattern = re.compile(r'\[([^\]\n]+)\]\(([^)\s\n]+)\)')
    staff = [(person['name'], person['bio']) for person in source['staff'] if pattern.search(person.get('bio') or '')]
    companies = [(company['name'], company['long_description']) for company in source['companies'] if pattern.search(company.get('long_description') or '')]
    assert [name for name, _ in staff] == ['Trevor Blackwell', 'Paul Graham', 'Jessica Livingston', 'Robert Morris']
    assert [name for name, _ in companies] == ['PostHog']
    for _, value in staff + companies:
        rendered = str(safe_markdown_links(value))
        assert rendered.count('<a href="') == len(pattern.findall(value))
        assert pattern.search(rendered) is None


def test_non_link_content_and_link_components_are_escaped():
    bio = '<script>alert(1)</script> [Founders <em>](https://example.com/book?a=1&b=2) <b>after</b>'
    rendered = str(safe_markdown_links(bio))
    assert rendered == '&lt;script&gt;alert(1)&lt;/script&gt; <a href="https://example.com/book?a=1&amp;b=2">Founders &lt;em&gt;</a> &lt;b&gt;after&lt;/b&gt;'
    assert '<script>' not in rendered
    assert '<em>' not in rendered
    assert '<b>' not in rendered


@pytest.mark.parametrize('url', [
    'javascript:alert',
    'data:text/html,payload',
    'mailto:test@example.com',
    '/relative/path',
    'https:///missing-host',
    'https://user:password@example.com/private',
])
def test_disallowed_markdown_link_target_is_not_activated(url):
    rendered = str(safe_markdown_links(f'<img src=x onerror=alert(1)> [Click me]({url})'))
    assert '<a ' not in rendered
    assert 'href=' not in rendered
    assert '<img' not in rendered
    assert '&lt;img src=x onerror=alert(1)&gt;' in rendered
    assert f'[Click me]({url})' in rendered
