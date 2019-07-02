#!/usr/bin/env python

"""
HTML helper functions

For creating HTML pages with data in a table
"""

import datetime
from lupp import fmt


def tr(text):
    """Create <tr> element with text in it"""
    h = f'\n<tr>{text}</tr>'
    return h


def td(text):
    """Create <td> with text in it"""
    h = f'<td>{text}</td>'
    return h


def tdr(text):
    """Create <td> with text right aligned in it"""
    h = f'<td align="right">{text}</td>'
    return h


def th(text, colspan=1):
    """Create <th> with text in it and optional colspan attribute"""
    t_colspan = "" if colspan == 1 else f" colspan={colspan}"
    h = f'<th{t_colspan}>{text}</th>'
    return h


def thr(text):
    """Create <th> with text right aligned in it"""
    h = f'<th align="right">{text}</th>'
    return h


def thl(text):
    """Create <th> with text left eligned in it"""
    h = f'<th align="left">{text}</th>'
    return h


def red(text):
    """Create <span> with text in it and with class={red}"""
    h = HTML.span(text, "red")
    return h


def bold(text):
    """Surround text with <b></b>"""
    h = f"<b>{text}</b>"
    return h


def italic(text):
    """Surround text with <i></i>"""
    h = f"<i>{text}</i>"
    return h


class HTML:
    """Class representing a HTML page as a string

    Class representing a HTML page as a string.
    Page consists of predefined header and footer, with customizable header and table content."""
    def __init__(self, col_count=5, header_font="Open Sans",
                 text_font="Open Sans"):
        self.col_count = col_count
        self.header_font = header_font
        self.text_font = text_font
        self.title = ""
        self.desc = ""
        self.stamp = ""
        self._table_cols = 1
        self._using_table = False

    def set_title_desc(self, title, desc):
        """Sets the header and description of the page"""
        self.title = title
        self.desc = desc

    def doc_header(self):
        """Initialze document header"""
        current = datetime.datetime.now()
        start_date_time = f"{fmt.dmyy(current)} {fmt.hm(current)}"
        url = "www.projektfredrika.fi"
        comment = f"Källa: http://{url} {start_date_time}"
        url = f'<a href="http://{url}">{url}</a>'
        self.stamp = u'Wikipedia-analys utförd av projekt Projekt Fredrika r.f. www.projektfredrika.fi'
        self.stamp = self.span(self.stamp, "ge_green")
        subhead = self.desc  # Was: start_date_time
        h1 = self.span(self.title, "ge_green")
        # noinspection PyPep8
        style = f"""\
 <style>
    p, th, td, li, .small {{font-family: {self.header_font}; }}
    h1, h2, h3, h4 {{font-family: {self.text_font}; }}
    a {{text-decoration: none;}}
    p {{font-size: 10pt; orphans: 3; widows: 3;
      margin-top: 0pt; margin-bottom: 0; padding-top: 0; line-height: 120%%;}}
    h1 {{font-size: 16pt; margin: 3pt 0 20px 0;}}
    h1 {{font-size: 16pt; margin: 3pt 0 5pt 0;}}
    h2, h3, h4 {{margin: 2pt 0 1pt 0; padding: 2pt 0 0 2pt;}}
    h2 {{font-size: 14pt; page-break-after: avoid; border-top: 0px solid black;}}
    h3 {{font-size: 12pt; border-top: 1px solid black;
        background-color: #8cba5c;}}
    h4 {{font-size: 10pt; border-top: 0px solid black;
        background-color: rgba(140,186,92,0.5);}}
    .subhead {{font-size: 13pt; margin-top: 0;}}
    .no_emph {{font-size: 9pt; font-weight:normal;}}
    .boilerplate {{font-size: 7pt; padding-top: 10pt;}}
    .columns {{-webkit-column-count: §col; -moz-column-count: §col;
        column-count: §col; column-gap: 2em;}}
    .ge_green {{color: #668d3c;}}
    .ge_lightest_green {{background-color: #8cba5c;}}
    .ge_red {{background-color: #cf3a27;}}
    .ge_blue {{background-color: #4e6172;}}
    .space {{line-height: 20%%;}}
    .small {{font-size:11pt; font-weight:normal; }}
    .red {{color: #cf3a27;}}
    .lr_tag {{font-style: italic; font-size: 8pt; }}
    @media print {{.ge_red {{color: #cf3a27;}} .ge_blue {{color: #4e6172;}}}}
    @page {{margin: 0.9cm 0.5cm 0.7cm 0.5cm;}}
 </style>
"""
        style = style.replace("§col", str(self.col_count))

        html_head = f"""\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<!--{comment}-->
<html>
<head>
 <title>{self.title}</title>
 <meta http-equiv="Content-type" content="text/html; charset=utf-8" />
{style}
</head>

<body>
 <article>
  <header>
   <p class="subhead">{subhead}</p>
   <h1>{h1}</h1>
  </header>
"""
        # <div class="columns">\n"""
        return html_head

    def doc_footer(self):
        """Initialize document footer"""
        footer = f'   <p class="boilerplate">{self.stamp}</p>'
        return f"   </div>\n{footer}\n </article>\n</body>\n</html>"

    def start_table(self, column_count=1):
        self._table_cols = column_count
        self._using_table = True
        return '\n\n<table>\n'

    def end_table(self):
        self._using_table = False
        return '\n\n</table>\n'

    @staticmethod
    def span(text, css_class):
        return f'<span class="{css_class}">{text}</span>'

    def _before(self):
        return f'<tr><td colspan="{self._table_cols}">' if self._using_table else ""

    def _after(self):
        return '</td></tr>' if self._using_table else ""

    def h2(self, text, cls=""):
        if not cls == "":
            cls = f" class='{cls}' "
        h = f'\n\n{self._before()}<h2{cls}>{text}</h2>{self._after()}\n'
        return h

    def h3(self, text, is_first=False):
        div_start = "" if is_first else "\n</div>"
        h = f'\n\n{self._before()}<h3>{text}</h3>{self._after()}\n'
        h = f'{div_start}\n{h}\n<div class="columns">'
        return h

    def h4(self, text, within_table=False):
        h = f'\n\n{self._before()}<h4>{text}</h4>{self._after()}\n'
        return h
