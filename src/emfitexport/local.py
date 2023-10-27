#!/usr/bin/env python
import re
from typing import Any, List, Dict
Stats = Dict[str, Any]

HTML_PRE = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<title>Emfit</title>
<link href="css/emfit.css" rel="stylesheet" type="text/css" />
</head>

<div id="shadow-one"><div id="shadow-two"><div id="shadow-three"><div id="shadow-four">
<div id="page">

<div style="padding:0 0 5px 5px"><img src="images/emfit.gif" alt="Emfit" /></div>

<div id="title"><div class="right"></div><span id="hello">&nbsp;</span></div>

<meta http-equiv="refresh" content="1">
'''.strip('\n') + '  \n'


# todo: do not hardcode numbers?
# note: the dots in few places are because there are tiny discrepancies sometimes? like \x00 or _ or dash, weird
RE_MID = '<big>HR:<big><big>(?P<hr>.*)</big></big></big>/min  .<p><big>RR:<big><big>(?P<rr>.*)</big></big></big>/min  .<p>.<p><small><small>00 21 77<br>t120 v2.2.1'

HTML_POST = '''
</small></small>
<div class="spacer">&nbsp;</div>
<div id="footer"></div>

</div></div></div></div></div>
</body>
</html>
'''

# TODO oof. should have used
# https://gist.github.com/harperreed/9d063322eb84e88bc2d0580885011bdd#dvmstatushtm
# dvmstatus.htm
def parse_page(html: str) -> Stats:
    if html == '':
        # weird, not sure why it happens sometimes.
        return dict(error='empty html')

    assert html.startswith(HTML_PRE)
    assert html.endswith(HTML_POST)
    html = html[len(HTML_PRE): -len(HTML_POST)]
    html = html.replace('\n', '') # just to simplify
    m = re.fullmatch(RE_MID, html)
    assert m is not None, repr(html)
    g = m.groupdict()

    hrs = g['hr']
    rrs = g['rr']

    hr = None if hrs == ' ---'  else float(hrs.strip())
    rr = None if rrs == ' --.-' else float(rrs.strip())
    return dict(
        hr=hr,
        rr=rr,
    )



from pathlib import Path
def process(d: Path):
    for x in sorted(d.glob('*.htm')):
        html = x.read_text()
        try:
            r = parse_page(html)
        except Exception as e:
            print(x)
            print(html)
            raise e
        else:
            print(r)

    # f = list(sorted(d.glob('*.htm')))[1000]
    # todo catch exceptions
    # todo always save htmls? for now manual cleanup?
