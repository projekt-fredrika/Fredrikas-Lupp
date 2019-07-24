#!/usr/bin/python3
"""
Main initalization script for fredrikas lupp.

First setups correct files to use and reads parameters
then calls different functions from lupp.scrape module.

"""

from wikitools.wiki import Wiki
from datetime import datetime
import sys
import os.path
import json
from pathlib import Path

from lupp import scrape, html, plot, utils

used_cache = {'cache': 'None', 'title': 'None'}
cache_path = Path("json") / "used_cache.json"
if cache_path.exists():
    used_cache = json.load(open(cache_path))
    used_cache['cache'] = Path(used_cache['cache'])

cnt_arg = len(sys.argv)

max_depth = 10 if cnt_arg < 5 else sys.argv[4]
languages = "sv|fi|en|de" if cnt_arg < 4 else sys.argv[3]
top_category = used_cache['title'] if cnt_arg < 3 else sys.argv[2]
cmd = "help" if cnt_arg < 2 else sys.argv[1]

jsonfile = Path(used_cache['cache']) if cnt_arg < 3 else utils.find_path(top_category)
errfile = jsonfile.with_name(f"err_{top_category}.json")

start = datetime.now()
print(f"python fredrikas_lupp.py {cmd} {top_category} {languages} "
      f"{max_depth} # {start.strftime('%d.%m.%Y kl. %H:%M')}\n")

# Wikimedia API fields
scalars = ['pagelanguage', 'touched', 'length', 'anoncontributors']
has_title = ['redirects', 'linkshere', 'links', 'images', 'categories']
other = ['contributors', 'langlinks', 'extlinks', 'revisions']
tricky = ['pageviews']
limits = ['rdlimit', 'lhlimit', 'pllimit', 'imlimit', 'cllimit', 'pclimit', 'lllimit', 'ellimit', 'pvlimit']
max_limits = {l: 500 for l in limits}
prop = "|".join(has_title + other + tricky + ['info'])
api_fields = {"scalars": scalars, "has_title": has_title, "other": other,
              "tricky": tricky, "prop": prop, 'max_limits': max_limits}
sites = {}
if cmd in ['scrape', 'scrapeb']:
    # only load sites if scraping, for painless use of other commands offline
    sites = {l: Wiki(f"https://{l}.wikipedia.org/w/api.php") for l in languages.split('|')}
blacklist = ['olympiska', 'användare', 'mall:']

d = {}  # this dict contains "everything"
e = {'timestamp': {}}  # this is for the error message and log time stamps

html = html.HTML()

if cmd == "scrape":
    if top_category == 'help':
        print('''
Run new scrape for CATEGORY and save josn file with the data.

Usage: python3 fredrikas_lupp.py scrape CATEGORY [languages] [max depth]

Example: python3 fredrikas_lupp.py scrape Nagu

Specify CATEGORY to scrape data from via madiawiki api, and save data as json file
in json/DATE/ directory. Also saves a more readable file of the data in pprint/DATE/
and a html file of the analyzed data in html/DATE/.

Scrape can also be used to scrape a specified list of pages, by instead of giving a category name
as CATEGORY, instead the name of a file can be supplied. The file needs to be a '.txt' file.
The script will then only scrape the pages that are listen inside that file.
The file should contain the page names on separate lines.

Example: python3 fredrikas_lupp.py scrape animals.txt

# animals.txt
Dog
Cat
Horse
Cow
#

Languages to use for the scraping can be specified after the category name as
a pipe ('|') separated list. Requires at least two languages. If not specified
'sv|fi|en|de' is the default and will be used.

Example: python3 fredrikas_lupp.py scrape Nagu 'sv|fi|dk|no'

Currently only supports using sv or fi as primary or secondary languages.

Max depth can be specified for how deep into subcategories the script will go.
Default is 10. To specify max depth, language also has to be specified.

Example: python3 fredrikas_lupp.py scrape Nagu 'sv|fi|en|de' 2
        ''')
        utils.exit_program(start)
    success = scrape.scrape_launch(d, e, sites, api_fields, max_depth, blacklist, top_category, languages)
    if not success:
        utils.exit_program(start)
    file_date = d['stats']['scrape_start'][:10]
    utils.save_json_file(jsonfile, d, dir_date=file_date)
    utils.save_json_file(errfile, e, dir_date=file_date)
    utils.save_used_cache(jsonfile)
    scrape.save_as_html(d, e, api_fields, top_category)
    scrape.save_as_html_lang(d, e, api_fields, top_category)

    utils.exit_program(start)

if cmd == "scrapeb":
    if top_category == 'help':
        print('''
Same as scrape, but only scrapes secondary language. Only for development use.
        ''')
    d = json.load(open(jsonfile))
    scrape.scrapeb_launch(d, e, max_depth, sites, blacklist, api_fields)

    file_date = d['stats']['scrape_start'][:10]
    utils.save_json_file(jsonfile, d, dir_date=file_date)
    utils.save_json_file(errfile, e, dir_date=file_date)
    utils.save_used_cache(jsonfile)
    scrape.save_as_html(d, e, api_fields, top_category)
    scrape.save_as_html_lang(d, e, api_fields, top_category)
    utils.exit_program(start)

if cmd == "use":
    if top_category == 'help':
        print('''
Analyze existing json file and select it to use it for next commands.

Usage: python3 fredrikas_lupp.py use CATEGORY

Example: python3 fredrikas_lupp.py use Nagu

Requires existing json file and does not request new data from any wiki. Analyzes data to create html
file in html/DATE/ direcotry and selects this categry as to be used for next command.
        ''')
        utils.exit_program(start)
    json_exists = os.path.isfile(jsonfile)
    if not json_exists:
        print(f"Filen {jsonfile} saknas. Ett rent faktum. Tyrckfel?")
        utils.exit_program(start)
    d = json.load(open(jsonfile))

    utils.save_used_cache(jsonfile)
    scrape.save_as_html(d, e, api_fields, top_category)
    scrape.save_as_html_lang(d, e, api_fields, top_category)
    print("---------------")
    file_date = d['stats']['scrape_start'][:10]
    utils.save_json_file(jsonfile, d, dir_date=file_date)
    utils.save_json_file(errfile, e, dir_date=file_date)

    utils.exit_program(start)

if cmd == "wikitext":
    if top_category == 'help':
        print('''
Analyze exisitng json file and create wikitext file from the data. Wikitext structure is the same as
html file created with use, except the formatting is wikitext markup instead of html.
File is saved under wikitext/DATE/ directory.
        ''')
        utils.exit_program(start)
    json_exists = os.path.isfile(jsonfile)
    if not json_exists:
        print(f"Filen {jsonfile} saknas. Ett rent faktum. Tyrckfel?")
        utils.exit_program(start)
    d = json.load(open(jsonfile))

    scrape.save_as_wikitext(d, e, api_fields, top_category, page_type='top100')
    print("---------------")
    utils.save_used_cache(jsonfile)

    utils.exit_program(start)

if cmd == 'page':
    if top_category == 'help':
        print('''
Show stats for a single page. Category first has to be choosen with 'use CATEGORY'

Usage: python3 fredrikas_lupp.py page Nagu
        ''')
        utils.exit_program(start)
    json_exists = os.path.isfile(used_cache['cache'])
    if not json_exists:
        print(f"Filen {used_cache['cache']} saknas. Ett rent faktum. Tyrckfel?")
        utils.exit_program(start)
    d = json.load(open(used_cache['cache']))
    page_name = f"{top_category} ({d['stats']['lang_1']})"
    print(f"\nInformation om sidan: {page_name}")
    try:
        print(scrape.wikitext_page(d, e, page_name, fmt='print'))
    except KeyError as ke:
        print(f"Hittade inte sidan {top_category}, använder du rätt cache - {used_cache['title']}?")
    utils.exit_program(start)

if cmd == 'analyze':
    if top_category == 'help':
        print('''
Visualize groth of CATEGORY based on existing json files. Produces pdf file with graph and
table showing the growth of a category over time. The file is saved in the analysis/ directory.
Requires atleast two json files for CATEGORY to be albe to produce a graph.

Usage: python3 fredrikas_lupp.py analyze CATEGORY
        ''')
        utils.exit_program(start)
    plot.save_plot(top_category, languages.split('|')[0])
    utils.exit_program(start)

try:
    d = json.load(open(jsonfile))
    title = d['stats']['category_title']
    lang = d['stats']['lang_1']
    print(f"Used cache: {title} ({lang})")
except FileNotFoundError as fe:
    # if subcommand is help, don't exit
    if top_category != 'help':
        print("Det finns ingen cache! Använd scrape <kategori> eller use <kategori> för att skapa en cache")
        utils.exit_program(start)
    else:
        pass


if cmd == "contributors":
    if top_category == 'help':
        print('''
Use existing json file to analyze contributors and create html file with the data.
Creates a list of contributors ordered based on number of contributions. The html file
is saved in html/DATE/.

Usage: python3 fredrikas_lupp.py contributors CATEGORY
        ''')
        utils.exit_program(start)
    scrape.analyse_and_save_contributors(d, e, top_category)

elif cmd == "contributors_w":
    if top_category == 'help':
        print('''
Use existing json file to analyze contributors and create wikitext file with the data.
Creates a list of contributors ordered based on number of contributions. The file
is saved in wikitext/DATE/.
Works the same as the command contributors except the saved file is in wikitext markup and not html.

Usage: python3 fredrikas_lupp.py contributors_w CATEGORY
        ''')
        utils.exit_program(start)
    scrape.analyse_and_save_contributors(d, e, top_category, fmt="wikitext")

elif cmd == "publish":
    if top_category == 'help':
        print('''
Connect to a mediawiki site and publish pages for CATEGORY. This will publish a base page for the category,
a contributors page, a top 100 page, and stats pages for each page belonging to the category.

Since editing a mediawiki requires signing in, credentials can either be provided via
enviroment variables WIKISITE, WIKIUSER, WIKIPASSWORD, or be inputted manually when running the script.

Usage: python3 fredrikas_lupp.py publish CATEGORY
        ''')
        utils.exit_program(start)
    if int(max_depth) == 0:
        scrape.publish(d, e, api_fields, top_category, subpages=False)
    else:
        scrape.publish(d, e, api_fields, top_category)

elif cmd == "list":
    if top_category == 'help':
        print('''
Print list of all json files the script can find. It will search for the files in json/DATE/,
where DATE is in the format 1970-01-01.

Usage: python3 fredrikas_lupp.py list
        ''')
        utils.exit_program(start)
    print("\nKategorier det finns json-dumpar för:\n")
    utils.list_json()

elif cmd == 'split':
    if top_category == 'help':
        print('''
Use existing json file and split the main category into all its direct subcategories,
creating separate files for all of them. Can be useful for dealing with massive categories.

Usage: python3 fredrikas_lupp.py split Nagu
        ''')
        utils.exit_program(start)
    print(f"Delar upp {top_category} i underkategorier:")
    scrape.split_category(d, e, top_category)

elif cmd == 'help':
    print('''
Fredriaks Lupp - Wikipedia analyzing tool

Usage: python3 fredrikas_lupp.py command CATEGORY [languages] [max_depth]

Fredriaks Lupp is a tool for analyzing categories or groups of pages
on wikipedia, to compare between languages, and find where improvement is needed.
It can also be used to automatically run scrapes and publish results
on a mediawiki site.

Example: python3 fredrikas_lupp.py scrape Nagu

Commands:
  scrape CATEGORY         Run new scrape for CATEGORY and save josn file with the data

  If CATEGORY contains '.txt' ending, instead of using a category, a list of pages will be used.
  THe list needs to be supplied as a text file named 'CATEGORY.txt'.

  use CATEGORY            Select existing josn file to analyze and use for next commands
  contributors CATEGORY   Use existing josn file and analyze contributors for that file
  contributors_w CATEGORY Use existing josn file and analyze contributors for that file
  publish CATEGORY        Connect to mediawiki site and publish pages for CATEGORY
  list                    Show list of existing josn files
  split CATEGORY          Use exisitng josn file and split main cateogry into all its subcategories
  page CATEGORY           Show stats for a single page. Category first has to be choosen with 'use CATEGORY'
  analyze CATEGORY        Visualize growth of CATEGORY based on existing josn files. Requires at least 2 files.

For more information about specific commands use: python3 frderikas_lupp.py command help


Languages to use for the scraping can be specified after the category name as
a pipe ('|') separated list. Requires at least two languages. If not specified
'sv|fi|en|de' is the default and will be used.

Example: python3 fredrikas_lupp.py scrape Nagu 'sv|fi|dk|no'

Currently only supports using sv or fi as primary or secondary languages.

Max depth can be specified for how deep into subcategories the script will go.
Default is 10. To specify max depth, language also has to be specified.

Example: python3 fredrikas_lupp.py scrape Nagu 'sv|fi|en|de' 2

    ''')
else:
    print(f"Unknown command {cmd}, try help")

utils.exit_program(start)
