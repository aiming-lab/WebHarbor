"""Render archived article prose without upstream widgets or network scripts."""
from html import escape
from html.parser import HTMLParser
import re


class ArticleHTML(HTMLParser):
    allowed = {'p', 'div', 'span', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'strong',
               'b', 'em', 'i', 'br', 'a', 'blockquote', 'table', 'tbody', 'tr',
               'th', 'td', 'figure', 'figcaption', 'img'}
    suppressed = {'script', 'style', 'template', 'noscript', 'iframe'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.hidden = 0
        self.finished = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'NewsletterKlaviyo' in values.get('class', ''):
            self.finished = True  # Scrape included the site's trailing signup/footer.
        if self.finished:
            return
        if tag in self.suppressed:
            self.hidden += 1
        if self.hidden or tag not in self.allowed:
            return
        attributes = ''
        if tag == 'a':
            href = values.get('href', '').replace('https://macyswineshop.com/', '/')
            if href.startswith(('/', 'https://', '#')) and not href.startswith('//'):
                attributes = f' href="{escape(href, quote=True)}"'
        if tag == 'img':
            src = values.get('src', '')
            if not src.startswith('/static/'):
                return  # Article hero is already supplied from the local archive.
            attributes = f' src="{escape(src, quote=True)}" alt="{escape(values.get("alt", ""), quote=True)}"'
        self.output.append(f'<{tag}{attributes}>')

    def handle_endtag(self, tag):
        if self.finished:
            return
        if tag in self.suppressed:
            self.hidden = max(0, self.hidden - 1)
            return
        if not self.hidden and tag in self.allowed and tag not in {'br', 'img'}:
            self.output.append(f'</{tag}>')

    def handle_data(self, data):
        if not self.finished and not self.hidden:
            self.output.append(escape(data))


def article_html(value):
    parser = ArticleHTML()
    parser.feed(value or '')
    return ''.join(parser.output)
