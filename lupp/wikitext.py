"""
Helpers for formatting wikitext
"""


def w_red(text):
    """Format text with the color red"""
    text = str(text)
    if '|' not in text[1:]:
        return f"| style='color:red' | {text}\n"
    else:
        parts = text.split('|')
        return f"|{parts[1]}style='color:red' | {parts[-1]}"


def w_bold(text):
    """Format text as bold"""
    parts = text.split(' ')
    if '\n' in parts[-1]:
        parts[-1] = parts[-1][:-1]
    return f"{' '.join(parts[:len(parts)-1])}'''{parts[-1]}'''\n"


def w_italic(text):
    """Format text as italics"""
    parts = text.split(' ')
    if '\n' in parts[-1]:
        parts[-1] = parts[-1][:-1]
    return f"{' '.join(parts[:len(parts)-1])}''{parts[-1]}''\n"


def align(text, align='right'):
    """Left or right align text"""
    text = str(text)
    if '|' not in text[1:]:
        return f"| align='{align}' | {text}\n"
    else:
        parts = text.split('|')
        return f"|{parts[1]}align='{align}' | {parts[-1]}"


def data_sort_type(text, type='number'):
    """Define data-sort-type for wikitext table auto sorting"""
    text = str(text)
    if '|' not in text[1:]:
        return f"| data-sort-type={type} | {text}\n"
    else:
        parts = text.split('|')
        return f"|{parts[1]}data-sort-type={type} | {parts[-1]}"


def colspan(text, cs=2):
    """Format colspan for text in wikitext table markup"""
    text = str(text)
    if '|' not in text[1:]:
        return f"| colspan='{cs}' | {text}\n"
    else:
        parts = text.split('|')
        return f"|{parts[1]}colspan='{cs}' | {parts[-1]}"


def rowspan(text, rs=2):
    """Format rowspan for text in wikitext table markup"""
    text = str(text)
    if '|' not in text[1:]:
        return f"| rowspan='{rs}' | {text}\n"
    else:
        parts = text.split('|')
        return f"|{parts[1]}rowspan='{rs}' | {parts[-1]}"


def cell(text):
    """Format text as a table cell for wikitext markup"""
    text = str(text)
    if text[0] == '|' or text[0] == '!':
        return text
    else:
        return f"| {text}\n"


def header(text):
    """Format text as a wikitext markup header"""
    if '|' not in text:
        return f"! {text}\n"
    else:
        return f"!{text[1:]}"


def table_start(h1, h2, cellpadding=0, cls='sortable'):
    """Create a wikitext markup table with headers and subheaders"""
    start = f"{{| cellpadding={cellpadding}px class='{cls}' |-\n"
    headers1 = [header(h) for h in list(h1)]
    headers2 = [header(data_sort_type(h)) for h in list(h2)]
    s = ''
    nr = '|-\n'
    return f"{start}{s.join(headers1)}{nr}{s.join(headers2)}{nr}"
