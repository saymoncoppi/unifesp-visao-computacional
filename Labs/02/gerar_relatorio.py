#!/usr/bin/env python3
"""Gera relatorio.html a partir de relatorio.md (sem dependencias externas)."""
import re, sys, os

def md_to_html(text):
    # Headers
    text = re.sub(r'^# (.+)$',   r'<h1>\1</h1>', text, flags=re.M)
    text = re.sub(r'^## (.+)$',  r'<h2>\1</h2>', text, flags=re.M)
    text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.M)

    # Bold / italic
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>', text)

    # Inline code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Code blocks
    text = re.sub(r'```[\w]*\n(.*?)```', r'<pre><code>\1</code></pre>',
                  text, flags=re.S)

    # Tables
    def convert_table(m):
        rows = [r.strip() for r in m.group(0).strip().split('\n') if r.strip()]
        html = ['<table>']
        for i, row in enumerate(rows):
            if re.match(r'^\|[-| :]+\|$', row):
                continue
            cells = [c.strip() for c in row.strip('|').split('|')]
            tag = 'th' if i == 0 else 'td'
            html.append('<tr>' + ''.join(f'<{tag}>{c}</{tag}>' for c in cells) + '</tr>')
        html.append('</table>')
        return '\n'.join(html)

    text = re.sub(r'(\|.+\|\n)+', convert_table, text)

    # Horizontal rule
    text = re.sub(r'^---+$', '<hr/>', text, flags=re.M)

    # Lists
    def convert_list(m):
        items = re.findall(r'^[-*] (.+)$', m.group(0), re.M)
        return '<ul>' + ''.join(f'<li>{i}</li>' for i in items) + '</ul>'
    text = re.sub(r'(^[-*] .+\n?)+', convert_list, text, flags=re.M)

    # Paragraphs (blank-line separated blocks that aren't already HTML)
    blocks = re.split(r'\n{2,}', text)
    result = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        if b.startswith('<'):
            result.append(b)
        else:
            result.append(f'<p>{b}</p>')

    return '\n'.join(result)


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    md_path   = os.path.join(base, 'relatorio.md')
    html_path = os.path.join(base, 'relatorio.html')

    with open(md_path, encoding='utf-8') as f:
        md = f.read()

    body = md_to_html(md)

    css = """
    body { font-family: Arial, sans-serif; max-width: 900px; margin: 40px auto;
           line-height: 1.6; color: #222; }
    h1 { color: #1a3a6b; border-bottom: 2px solid #1a3a6b; padding-bottom: 6px; }
    h2 { color: #1a3a6b; margin-top: 36px; }
    h3 { color: #2a5298; }
    table { border-collapse: collapse; width: 100%; margin: 16px 0; }
    th, td { border: 1px solid #aaa; padding: 8px 12px; text-align: left; }
    th { background: #dce6f1; }
    tr:nth-child(even) { background: #f5f8fc; }
    code { background: #f0f0f0; padding: 2px 5px; border-radius: 3px;
           font-family: monospace; font-size: 0.9em; }
    pre { background: #f4f4f4; padding: 14px; border-left: 4px solid #1a3a6b;
          overflow-x: auto; }
    pre code { background: none; padding: 0; }
    hr { border: none; border-top: 1px solid #ccc; margin: 30px 0; }
    em { color: #555; }
    """

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Laboratório 02 — Detecção de Pratos com Transformada de Hough</title>
  <style>{css}</style>
</head>
<body>
{body}
</body>
</html>"""

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Gerado: {html_path}")
    print("Para converter em PDF: abra o HTML no navegador e use Ctrl+P → Salvar como PDF")
    print("Ou execute: libreoffice --headless --convert-to pdf relatorio.html")


if __name__ == '__main__':
    main()
