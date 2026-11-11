"""Bounded public-page diagnostics; no ranking or recommendation score."""
from html.parser import HTMLParser
import re
from urllib.parse import urlsplit, urlunsplit

VERSION = 'agent-readable-content-v1'
NUMBER = re.compile(r'[$€¥￥]\s*\d[\d,.]*|\b\d+(?:\.\d+)?\s*(?:mm|cm|kg|g|khz|hz|dpi)\b', re.I)


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []; self.parts = []; self.headings = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = bool(self.stack and self.stack[-1][1]) or tag in {'script', 'style', 'template', 'noscript', 'head'} or 'hidden' in attrs or attrs.get('aria-hidden') == 'true' or bool(re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', attrs.get('style', ''), re.I))
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, hidden))

    def handle_endtag(self, tag):
        for index in range(len(self.stack)-1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]; break

    def handle_data(self, value):
        value = ' '.join(value.split())
        if value and not (self.stack and self.stack[-1][1]):
            self.parts.append(value)
            if any(tag in {'h1', 'h2', 'h3', 'dt', 'summary'} for tag, _ in self.stack): self.headings.append(value)


def numbers(text):
    return sorted({re.sub(r'\s+', '', item).lower() for item in NUMBER.findall(text)})


def scan(fetcher, url):
    parsed = urlsplit(url)
    checks, captures = [], []
    def add(id, title, passed, detail, required=False):
        checks.append(dict(id=id, title=title, passed=passed, detail=detail, required=required))
    html = None
    for kind, target in [('html', url), ('markdown', urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip('/') + '.md', '', ''))), ('llms', urlunsplit((parsed.scheme, parsed.netloc, '/llms.txt', '', '')))]:
        try:
            capture = fetcher(target); captures.append(capture)
            body = capture['body']; ok = 200 <= capture['status'] < 300
            if kind == 'html':
                valid = ok and bool(re.search(r'<(?:html|main|body|h1)\b', body, re.I))
                add('html', '产品 HTML 可访问', valid, f'{target} · HTTP {capture["status"]}', True)
                if not valid: continue
                parser = VisibleHTML(); parser.feed(body); html = ' '.join(parser.parts)
                add('visible_text', '原始 HTML 含可提取正文', len(html) >= 80, f'{len(html)} 字符；不执行 JS，不检测外部 CSS，不代表浏览器视觉验收。', True)
                tokens = numbers(html)
                add('fact_clues', '正文参数／价格文字线索', None, f'提取 {len(tokens)} 个数值线索：' + ', '.join(tokens[:20]) + '；须按型号、版本、市场与权威来源核对，不能认定事实正确。')
                questions = [line for line in parser.headings if '?' in line or '？' in line or re.search(r'FAQ|常见问题', line, re.I)]
                add('faq', '直接答案与 FAQ 入口', True if questions else None, '标题线索：' + ' / '.join(questions[:3]) if questions else '未识别问答标题；需检查实际需求是否得到直接回答，无需每页强加 FAQ。')
            elif kind == 'markdown':
                valid = ok and capture.get('content_type', '').split(';')[0] in {'text/plain', 'text/markdown', 'text/x-markdown'} and not re.search(r'<(?:!doctype|html|body|script)\b', body, re.I) and len(body.strip()) >= 30
                add('markdown', '可选 Markdown 真实可读', True if valid else None, target + ('；已取得文本。' if valid else '；缺失、出错或返回 HTML，不能当作已提供 Markdown；不因此扣分。'))
                if valid and html is not None:
                    html_tokens, md_tokens = set(numbers(html)), set(numbers(body))
                    add('markdown_consistency', 'HTML / Markdown 数值线索差异', None if html_tokens != md_tokens else True, '仅比较价格／单位数值集合，不证明语义或事实一致。差异需逐字段核对：' + ', '.join(sorted(html_tokens ^ md_tokens)[:30]))
            else:
                valid = ok and capture.get('content_type', '').startswith('text/') and not re.search(r'<(?:!doctype|html|body|script)\b', body, re.I) and bool(re.search(r'https?://|\]\(', body))
                add('llms', '可选 llms.txt 文本索引', True if valid else None, target + '；可选 Agent 入口，不证明被采用；Google 不以此提升可见性。')
        except (OSError, ValueError) as error:
            add(kind, '采集异常：' + kind, False if kind == 'html' else None, str(error)[:180], kind == 'html')
    for id, title, detail in [('facts_review', '事实与图表核对', '图表数据需文字等价表达；字段逐项核对来源，37g/39g 冲突继续省略。'), ('intent_review', '场景页／对比页的独立价值', '核对是否解决真实选购、替代、操作、事实需求；合并仅改关键词的重复页。'), ('external_review', '外部独立证据', '检查真实评测与使用经验；不以刷提及或第三方数量认定推荐提升。'), ('measurement', '效果测量分离', '抓取日志、AI 引荐访问、回答引用、推荐与事实正确率分别记录；联网固定题组保存实际回答和引用 URL，未联网 API 仅作独立基线。')]:
        add(id, title, None, detail)
    return {'version': VERSION, 'scope': 'raw_html_readability_signals_not_fact_or_geo_score', 'checks': checks}, captures
