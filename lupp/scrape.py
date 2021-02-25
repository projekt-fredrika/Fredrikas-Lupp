"""
Scripts for scraping data about wikipedia categories and pages via wikimedia API ({lang}.wikipedia.org/w/api.php)

The main functions for scraping are scrape_launch and scrapeb_launch

All functions use a 'global' dict d where all the data is saved. An example of the dict strucuture:
d {
    'blacklist': {}
    'categories': { 'Category:Example (en)': { 'order': 1,
                        'pages': { 'example1 (en)' : {'title_en': 'example1'}
                        },
                        'title_en': 'Category:Example'
                    },
    }
    'pages': { 'Category:Example1 (en)': {
                    'categories': [],
                    'contributors': ['Name1', 'Name2',],
                    'extlinks': [],
                    'images': [],
                    'is_category': False,
                    'langlinks': [],
                    'length': 140,
                    'links': [],
                    'linkshere': [],
                    'pagelanguage': 'en',
                    'pageviews': {date: 0},
                    'redirects': [],
                    'revisions': [],
                    'sections': [],
                    'stats': {'categories_cnt': '0',
                              'contributors_cnt': '4',
                              'contributors_tot': '4',
                              'extlinks_cnt': '0',
                              'images_cnt': '0',
                              'langlinks_cnt': '2',
                              'len_sv': '142',
                              'links_cnt': '0',
                              'linkshere_cnt': '0',
                              'pageviews_sv': '3',
                              'pageviews_tot': '2',
                              'quality': 12,
                              'redirects_cnt': '0',
                              'revisions_cnt': '0',
                              'total_langs': 2},
                    'title': 'Category:Example1 '
                    'touched': '2018-06-21 '
                               '15:43:50'},

            }
    }
    'stats': {'categories_cnt': 1,
           'category_title': 'Example1',
           'date_from': '2019-04-14',
           'date_to': '2019-06-12',
           'lang_1': 'en',
           'lang_2': 'fi',
           'languages': 'en|fi|sv|de',
           'pages_cnt': 1,
           'pv_days': 60,
           'response_time_s': '23',
           'scrape_start': '2019-06-14 12:56:56',
           'scraped': '2019-06-14 12:57:20'}}
}

Also contains methods for saving data from scrape in different formats,
using save_as_html, asve_as_html_lang, save_as_wikitext and analyze__and_save_contributors

Also contains some utility functions for dealing with publishing the result of a scrape to a mediawiki site.
"""

import codecs
import csv
import os
import sys
import concurrent.futures
import copy
from datetime import datetime
from pathlib import Path

from wikitools import exceptions, wiki, api, page

from lupp.html import HTML, tr, th, thl, tdr, td, red, bold, italic
from lupp.html import graph, graph_bar, action_box
from lupp.utils import now_ymd_hms, days_between, loading_bar, save_utf_file, save_json_file, get_utf_file
from lupp.wikitext import table_start, align, cell, rowspan, colspan, w_red, w_bold, w_italic
from functools import cmp_to_key


def scrape_launch(d, e, sites, api_fields, max_depth, blacklist, category_title, languages="sv|fi|en|de"):
    """Setup basic data in d and start scraping category from category_title.

    Setup basic data in d and call _scrape_category(..) or _scrape_atricle_list(..) to start retrieving data.
    _scrape_pages(..) calls will be run 'concurrently' in own threads to optimize for network latency of the requests.

    Lastly data from d will be analyzed with additional data also saved in d.

    :param d: 'global' dict containing stats and all data about current scrape
    :param e: 'global' dict containing error data and logging info
    :param sites: dict with wikitools Wiki objects that the scrape retrieves data from
    :param api_fields: dict with all parameters for use with API requests
    :param max_depth: How deep the scrape will go into subcategories
    :param blacklist: list of titles of pages that will be skipped, for example User or Discussion pages
    :param category_title: Title for main category to be scraped
    :param languages: '|' separated list of languages to be considered
    :return: boolean idicating if an error occured or if the scrape completed successfully
    """
    # Scrape = read Wikipedia data from web, store in overall dict d, then save it for later analysis
    d['stats'] = {}
    d['blacklist'] = {}
    d['categories'] = {}
    d['pages'] = {}

    lang = languages.split("|")[0]

    d['stats']['category_title'] = category_title
    d['stats']['languages'] = languages
    d['stats']['lang_1'] = lang
    d['stats']['lang_2'] = languages.split("|")[1]
    d['stats']['categories_cnt'] = 0
    d['stats']['pages_cnt'] = 0
    d['stats']['scrape_start'] = now_ymd_hms()

    start = datetime.now()

    is_article_list = ".txt" in category_title

    if is_article_list:
        _scrape_article_list(d, e, sites, api_fields, category_title)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as tpe:
            _scrape_lang(d, e, api_fields, "*", "en", tpe=tpe)
    else:
        # Loading bar while scraping pages
        loading = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        loading_status = {'status': True}
        loading.submit(loading_bar, loading_status, d)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as tpe:
            try:
                _scrape_category(d, e, max_depth, sites, blacklist,
                                 api_fields, category_title, lang, tpe=tpe)
            except exceptions.APIError as we:
                e['error_scrape_category wiki'] = {'info': we.args, }
                print(f"wikitools API-fel {we.args}")
                if "invalidcategory" in we.args:
                    print("Felaktig kategori, avbryter programmet")
                    return False

            try:
                _scrape_missing_primary_language(d, e, max_depth, sites, blacklist, api_fields, tpe=tpe)
            except exceptions.APIError as we:
                e['error_scrape_missing_primary_language wiki'] = {'info': we.args, }
                print(f"wikitools API-fel {we.args}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as tpe:
            try:
                _scrape_lang(d, e, api_fields, languages, lang, tpe=tpe)
            except exceptions.APIError as we:
                e['error_scrape_lang wiki'] = {'info': we.args, }
                print(f"wikitools API-fel {we.args}")

        loading_status['status'] = False
        loading.shutdown(wait=False)
    try:
        analyse_pagestats(d, e, api_fields)
        analyse_langstats(d, e)
        analyse_time_interval(d, e)
    except KeyError as ke:
        e['error_analyze'] = {'info': ke.args, }
        print(f'Could not analyze, the pages are missing data')
        if len(d['pages']) < 3:
            print("\nVery small cetegory with inaccurate data, category wll not be saved")
            return False

    end = datetime.now()
    d['stats']['response_time_s'] = str((end - start).seconds)
    scraped = now_ymd_hms()
    d['stats']['scraped'] = scraped
    return True


def scrapeb_launch(d, e, max_depth, sites, blacklist, api_fields):
    """Same as scrape_launch except only checks secondary language from main category"""

    # only started by developer (never end user), to save on response time while debugging/coding
    start = datetime.now()

    # scrape_lang()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as tpe:
            _scrape_missing_primary_language(d, e, max_depth, sites, blacklist, api_fields)
    except exceptions.APIError as we:
        e['error_scrape_category wiki'] = {'info': we.args, }
        print(f"wikitools API-fel {we.args}")
    try:
        analyse_pagestats(d, e, api_fields)
        analyse_langstats(d, e)
        analyse_time_interval(d, e)
    except KeyError as ke:
        e['error_analyze'] = {'info': ke.args, }
        print(f'Kunde inte analysera, det fattas data från sidorna')

    end = datetime.now()
    d['stats']['response_time_s'] = str((end - start).seconds)
    scraped = now_ymd_hms()
    d['stats']['scraped'] = scraped


def _scrape_category(d, e, max_depth, sites, blacklist, api_fields,
                     category_title, lang, depth=0, add_prefix=True, add_to_category=None, force=False, tpe=None):
    """Recursively retrieve stats about {category_title} from {lang}.wikipedia.org and save data in d.

    Recursively go through all pages and subcategories in category {category_title} on wikipedia
    in language based on lang. All categories and pages in the categories will be saved in the d dict.

    :param add_prefix: If wikipedia Category: needs to be added before title
    :param add_to_category: If this page belongs to a category, true for all subcategories
    :param force: Force program to retrieve info about category again, even though it might already exist
    :param tpe: ThreadPoolExecutor for running _scrape_pages(..) calls in own threads
    :return: None
    """
    # recursively scrape a category and its sub-categories
    if add_prefix:
        category_title = f"Kategori:{category_title}"
    full_title_lang = f"{category_title} ({lang})"
    e['timestamp'][full_title_lang] = now_ymd_hms()
    category_exists = full_title_lang in d['categories']
    if category_exists and not force:
        # print(f"\r- Category titled {full_title_lang} already exists, skipping") TODO: proper logging
        return
    # only scrape page and not category if max_depth reached
    elif depth >= int(max_depth):
        tpe.submit(_scrape_pages, d, e, api_fields, category_title, lang, is_category=True)
        return

    # print(f"\rCategory title: {category_title}") TODO: proper logging

    d['stats']['categories_cnt'] += 1
    category_itself = f"{category_title} ({lang})"
    title_lang = f'title_{lang}'
    d['categories'][full_title_lang] = {title_lang: category_title,
                                        'pages': {category_itself: {title_lang: category_title}},
                                        'order': d['stats']['categories_cnt']}
    tpe.submit(_scrape_pages, d, e, api_fields, category_title, lang, is_category=True)

    site = sites[lang] = wiki.Wiki(f"https://{lang}.wikipedia.org/w/api.php")
    params = {'action': 'query', 'cmtitle': category_title,
              'list': 'categorymembers', 'cmlimit': 500}

    request = api.APIRequest(site, params)
    p_to_scrape = {}
    for language in d['stats']['languages'].split('|'):
        p_to_scrape.update({language: []})
    # Create batches of results on top-level category
    for result in request.queryGen():  # async_gen(request.queryGen):
        pages = result['query']['categorymembers']

        # -print(f"pages {pages}")

        # Loop individual pages within top-level category
        for p in pages:
            # -print(f"p {p} ")
            title = p['title']
            page_is_category = p['ns'] != 0

            # Skip blacklisted titles (which are considered spam)
            if not all([b not in title.lower() for b in blacklist]):
                continue

            # Append page title to category list
            full_title = title
            p_ftl = f"{full_title} ({lang})"
            # -print(f"full_title_lang {full_title_lang} p_ftl {p_ftl} title_lang {lang}")
            if add_to_category is None:
                d['categories'][full_title_lang]['pages'][p_ftl] = {title_lang: title}
            else:
                lang_1_category_pages = d['categories'][add_to_category]['pages']
                lang_2_page_exists = p_ftl in lang_1_category_pages
                if not lang_2_page_exists:
                    lang_1_category_pages[p_ftl] = {title_lang: title}

            if page_is_category:
                try:
                    _scrape_category(d, e, max_depth, sites, blacklist,
                                     api_fields, title, lang, depth=depth + 1, add_prefix=False, tpe=tpe)
                except exceptions.APIError as we:
                    e['error_scrape_category wiki'] = {'info': we.args, }
                    print(f"wikitools API-fel {we.args}")
                    pass
            else:
                p_to_scrape[lang] += [title]
    for b_l in p_to_scrape:
        batch = p_to_scrape[b_l]
        # cut batch size to 50
        for i in range(0, len(batch), 50):
            batch_string = '|'.join(batch[i:i + 50])
            tpe.submit(_scrape_pages, d, e, api_fields, batch_string, b_l, is_category=False, quickscan=False)


def _scrape_article_list(d, e, sites, api_fields, filename, lang="en"):
    """Scrape pages from list of different pages

    Reads a list of pages from text file and scrapes the pages. Works in priciple the same as _scrape_category(..),
    only creates a mock category based on the file of the text file and adds all pages to that category in the global
    data dict. The file needs to be '.txt' and contain the names of the categories on separate lines.
    Starts with scraping the pagex in the main lang.
    """
    # instead of a category, scrape individual articles listed in a file
    header_title_lang = f"{filename} ({lang})"
    e['timestamp'][header_title_lang] = now_ymd_hms()

    print(f"File list: {filename}")

    d['stats']['categories_cnt'] += 1
    category_itself = f"{filename} ({lang})"
    title_lang = f'title_{lang}'
    d['categories'][header_title_lang] = {title_lang: filename,
                                          'pages': {category_itself: {title_lang: filename}},
                                          'order': d['stats']['categories_cnt']}
    if os.path.exists(filename):
        with codecs.open(filename) as f:
            articles = f.readlines()
        # remove whitespace characters like `\n` at the end of each line
        articles = [x.strip() for x in articles]
    else:
        print(f"Filen {filename} saknas")
        sys.exit()
    site = sites[lang] = wiki.Wiki(f"https://{lang}.wikipedia.org/w/api.php")

    titles = '|'.join(articles)
    # print(f'Checking {len(articles)} pages') TODO: proper logging
    is_category = False
    for full_title in articles:
        # print(f"Article {full_title}") TODO: proper logging
        full_title_lang = f"{full_title} ({lang})"
        # print(f"full_title_lang {full_title_lang}") TODO: proper logging
        d['stats']['pages_cnt'] += 1
        d['pages'][full_title_lang] = {'title': full_title,
                                       'is_category': is_category}

        # Append page title to "category" list (in fact: article list)
        p_ftl = f"{full_title} ({lang})"
        d['categories'][header_title_lang]['pages'][p_ftl] = {title_lang: full_title}

        # Create empty list for all list type fields
        for fld in api_fields["has_title"] + api_fields["other"]:
            d['pages'][full_title_lang][fld] = []

        params = {'action': 'query', 'titles': full_title, 'prop': api_fields['prop'], **api_fields['max_limits']}
        req_links = api.APIRequest(site, params)
        j = 0
        # Create batches of results on individual items within page
        for sub_result in req_links.queryGen():  # async_gen(req_links):
            j += 1
            pages = sub_result['query']['pages']
            for page_id in list(pages):
                if page_id == '-1':
                    # print(f'Page {pages[page_id]["title"]} does not exist')  TODO: proper logging
                    continue
                pageinfo = pages[page_id]
                # Loop individual scalar fields
                if j == 1:
                    for fld in api_fields["scalars"]:
                        if fld in pageinfo:
                            val = pageinfo[fld]
                            if fld == 'touched':
                                val = val.replace("T", " ").replace("Z", "")
                            d['pages'][full_title_lang][fld] = str(val)

                # Calculate page views (with peculiar MediaWiki structure)
                if 'pageviews' in pageinfo:
                    a_dict = pageinfo['pageviews']
                    d['pages'][full_title_lang]['pageviews'] = a_dict

                if 'contributors' in pageinfo:
                    for item in pageinfo['contributors']:
                        d['pages'][full_title_lang]['contributors'].append(item['name'])

                if 'langlinks' in pageinfo:
                    for item in pageinfo['langlinks']:
                        lang_item = {item['lang']: item['*']}
                        d['pages'][full_title_lang]['langlinks'].append(lang_item)

                # Loop individual non-scalar fields with 'title'
                for fld in api_fields["has_title"]:
                    if fld in pageinfo:
                        for item in pageinfo[fld]:
                            d['pages'][full_title_lang][fld].append(item['title'])
                if 'extlinks' in pageinfo:
                    for item in pageinfo['extlinks']:
                        d['pages'][full_title_lang]['extlinks'].append(item['*'])

    # print(f"\r({[len(d['pages'][f'{ftl} ({lang})']['langlinks']) for ftl in articles]} langs)") TODO: proper logging


def _scrape_sections(d, e, title, lang):
    """Scrape all sections of a page

    Scrape all sections of a page and add them to the global dict.
    Page is specified via :param title and :param lang."""
    # scrape section headers on individual page
    full_title_lang = f"{title} ({lang})"
    site = wiki.Wiki(f"https://{lang}.wikipedia.org/w/api.php")
    params = {'action': 'parse', 'page': title}
    req_links = api.APIRequest(site, params)
    d['pages'][full_title_lang]['sections'] = []
    for sub_result in req_links.queryGen():  # async_gen(req_links):
        sections = sub_result['parse']['sections']
        for section in sections:
            toclevel = section['toclevel']
            header = section['line']
            dashes = (toclevel - 1) * "-"
            d['pages'][full_title_lang]['sections'].append(dashes + header)


def _scrape_revisions(d, e, title, lang):
    """scrape edit history of individual page

    Scrape edit history of individual page. Saves user, timestamp and comment of every revision to the page
    since 2017-01-01.
    Page is specified via :param title and :param lang.
    """
    full_title_lang = f"{title} ({lang})"
    site = wiki.Wiki(f"https://{lang}.wikipedia.org/w/api.php")
    params = {'action': 'query', 'titles': title, 'prop': 'revisions',
              'rvprop': 'timestamp|user|comment', 'rvdir': 'newer',
              'rvstart': '2017-01-01T00:00:00Z', 'rvlimit': 500}
    req_links = api.APIRequest(site, params)
    d['pages'][full_title_lang]['revisions'] = []
    for sub_result in req_links.queryGen():  # async_gen(req_links):
        pages = sub_result['query']['pages']
        page = pages[list(pages)[0]]
        if 'revisions' in page:
            revisions = page['revisions']
            for revision in revisions:
                d['pages'][full_title_lang]['revisions'].append(revision)


def _scrape_pages(d, e, api_fields, titles, lang, is_category, quickscan=False):
    """Scrape a batch of pages

    Scrape a batch of pages and save the information in the global dict.
    Page batch size should optimally be 50 to optimize number of api requests needed.

    :param d: 'global' dict where all data is saved
    :param e: 'global' error dict where timestamps and errors are logged
    :param api_fields: what parameters are passed to the api requests
    :param titles: pipe ('|') separated string with all the page titles to be scraped
    :param lang: From which wiki the pages are requested from, eg. sv, en
    :param is_category: If this page is a category page, eg. Category: Finland
    :param quickscan: If false, skips to save data from api_fields['has_title']
    :return: None
    """
    full_titles = titles.split('|')
    for full_title in full_titles.copy():
        full_title_lang = f"{full_title} ({lang})"
        page_exists = full_title_lang in d['pages']
        if page_exists:
            full_titles.remove(full_title)
            continue
        d['stats']['pages_cnt'] += 1
        d['pages'][full_title_lang] = {'title': full_title,
                                       'is_category': is_category}
        # Create empty list for all list type fields
        for fld in api_fields["has_title"] + api_fields["other"]:
            d['pages'][full_title_lang][fld] = []
    # skipping already existing pages
    if not full_titles:
        return
    titles = '|'.join(full_titles)
    # print(f'scrape_pages {full_titles}') TODO: proper logging

    site = wiki.Wiki(f"https://{lang}.wikipedia.org/w/api.php")
    params = {'action': 'query', 'titles': titles, 'prop': api_fields['prop'], **api_fields['max_limits']}
    req_links = api.APIRequest(site, params)
    j = 0
    # Create batches of results on individual items within page
    for sub_result in req_links.queryGen():  # async_gen(req_links):
        j += 1
        pages = sub_result['query']['pages']
        # page_id = list(pages)[0]
        for page_id in list(pages):
            if page_id == '-1':
                # print(f'Sidan {pages[page_id]["title"]} finns inte') TODO: proper logging
                continue
            pageinfo = pages[page_id]
            full_title_lang = f"{pageinfo['title']} ({lang})"
            # print(f"page_id {page_id} title {full_title_lang} j {j}")
            # Loop individual scalar fields
            if j == 1:
                for fld in api_fields["scalars"]:
                    if fld in pageinfo:
                        val = pageinfo[fld]
                        if fld == 'touched':
                            val = val.replace("T", " ").replace("Z", "")
                        d['pages'][full_title_lang][fld] = str(val)

            # Calculate page views (with peculiar MediaWiki structure)
            if 'pageviews' in pageinfo:
                a_dict = pageinfo['pageviews']
                d['pages'][full_title_lang]['pageviews'] = a_dict

            if 'contributors' in pageinfo:
                for item in pageinfo['contributors']:
                    d['pages'][full_title_lang]['contributors'].append(item['name'])

            if 'langlinks' in pageinfo:
                for item in pageinfo['langlinks']:
                    lang_item = {item['lang']: item['*']}
                    d['pages'][full_title_lang]['langlinks'].append(lang_item)

            if not quickscan:
                # Loop individual non-scalar fields with 'title'
                for fld in api_fields["has_title"]:
                    if fld in pageinfo:
                        for item in pageinfo[fld]:
                            d['pages'][full_title_lang][fld].append(item['title'])
                if 'extlinks' in pageinfo:
                    for item in pageinfo['extlinks']:
                        d['pages'][full_title_lang]['extlinks'].append(item['*'])
            if j == 1:
                _scrape_sections(d, e, pageinfo['title'], lang)
                _scrape_revisions(d, e, pageinfo['title'], lang)

    # print(f"\r({[len(d['pages'][f'{ftl} ({lang})']['langlinks']) for ftl in full_titles]} langs)")TODO: proper logging


def _scrape_lang(d, e, api_fields, langs, primary_lang, tpe=None):
    """Scrape all pages in main category, (or page list) in other languages

    Scrape all pages in main category in other languages. If :param langs is '*',
     all available languages will be scraped, else only specified languages will be scraped."""
    limited_langs = langs != "*"
    other_langs = []
    if limited_langs:
        other_langs = langs.split('|')
        other_langs.remove(primary_lang)
    l_categories = list(d['categories'])
    l_categories.sort(key=lambda x: d['categories'][x]['order'])
    for title in l_categories:
        p_to_scrape = {}
        if limited_langs:
            # initialise pages to scrape
            p_to_scrape = {l: [] for l in other_langs}

        pages = d['categories'][title]['pages']
        # print(f"\rscrape_lang: Category {title}") TODO: proper logging
        is_category = False
        for p in pages:
            if p not in d['pages']:
                continue
            is_category = d['pages'][p]['is_category']
            for l in d['pages'][p]['langlinks']:
                lang = list(l)[0]
                # disregard small complex languages with codes > 3 chars
                lang_ok = len(lang) < 4 or lang == "simple"
                if not lang_ok:
                    continue
                if lang not in p_to_scrape:
                    p_to_scrape[lang] = []
                if limited_langs:
                    if lang not in other_langs:
                        continue
                l_title = l[lang]
                # check if link is header on page and scan whole page
                if '#' in l_title:
                    hashtag_index = l_title.index('#')
                    l_title = l_title[:hashtag_index]
                p_to_scrape[lang] += [l_title]
        p_to_scrape = {k: v for k, v in p_to_scrape.items() if v}
        # print(f"p_to_scrape {p_to_scrape}") TODO: proper logging
        for b_l in p_to_scrape:
            batch = p_to_scrape[b_l]
            # cut batch size to 50 to retrieve 50 pages at a time from the API
            for i in range(0, len(batch), 50):
                batch_string = '|'.join(batch[i:i + 50])
                tpe.submit(_scrape_pages, d, e, api_fields, batch_string, b_l, is_category, quickscan=False)


def _scrape_missing_primary_language(d, e, max_depth, sites, blacklist, api_fields, tpe=None):
    """Try to recursively scrape main category in second language

    Try to recursively scrape main category in second language. First try to find main category page in second language,
    then start new _scrape_category(..) for that category in second language.

    Done to find pages that exist in second language missing from primary lnaguage."""
    l_categories = list(d['categories'])
    l_categories.sort(key=lambda x: d['categories'][x]['order'])
    # create a list of pages in the desired order
    for category_title in l_categories:

        # Find category second lang
        second_lang_title = ""
        # todo-me: underliga if-tester
        if category_title not in d['pages']:
            # print(f"**** Category title {category_title} not in d[''pages'']") TODO: proper logging
            continue
        if 'langlinks' not in d['pages'][category_title]:
            continue
        for l in d['pages'][category_title]['langlinks']:
            lang = list(l)[0]
            # if lang not in "fi en de fr no dk ru":
            if lang == d['stats']['lang_2']:
                second_lang_title = l[lang]
                break
        if second_lang_title == "":
            continue
        # print(f"\rChecking category {second_lang_title} in secondary language matching category {category_title}")
        # TODO: proper logging

        # Read the entire 'fi' category "once again" (to catch missing pages)
        _scrape_category(d, e, max_depth, sites, blacklist, api_fields, second_lang_title,
                         d['stats']['lang_2'], add_prefix=False, add_to_category=category_title, force=True, tpe=tpe)


def analyse_pagestats(d, e, api_fields):
    """Analyze data scraped and create 'stats' dict for each page.

    Analyze data scraped and create 'stats' dict for each page. The stat dict contains:
     'stats': {'categories_cnt': '3',
          'contributors_cnt': '7',
          'contributors_tot': '7',
          'extlinks_cnt': '5',
          'images_cnt': '4',
          'langlinks_cnt': '1',
          'len_sv': '4444',
          'links_cnt': '36',
          'linkshere_cnt': '2',
          'pageviews_sv': '1',
          'pageviews_tot': '1',
          'quality': 84,
          'redirects_cnt': '0',
          'revisions_cnt': '3',
          'total_langs': 1},

    Quality is a value calculated based on different aspects of the page, for example length, image count,
    number of different language links, external links etc. The rest of the stats are directly taken from the
    scraped data.

    """
    def points(statistic):
        return int(stats[statistic])

    l_pages = list(d['pages'])
    for p in l_pages:
        d['pages'][p]['stats'] = {}
        d['pages'][p]['lang_stats'] = {}
        stats = d['pages'][p]['stats']
        lang_stats = d['pages'][p]['lang_stats']
        anon = int(d['pages'][p].get('anoncontributors', 0))
        known = len(d['pages'][p]['contributors'])
        stats['contributors_tot'] = str(anon + known)

        # Zero the counters for the page
        count = {}
        vals = {}
        for fld in [field for types in api_fields.values() for field in types]:
            count[fld] = 0
            vals[fld] = ""

        # Loop individual non-scalar fields
        for fld in api_fields["has_title"] + api_fields["other"]:
            if fld in d['pages'][p]:
                cnt = len(d['pages'][p][fld])
                count[fld] += cnt
                stats[fld + "_cnt"] = str(count[fld])
        # Calculate page views (with peculiar structure)
        cnt = 0
        if 'pageviews' in d['pages'][p]:
            a_dict = d['pages'][p]['pageviews']
            a_list = list(a_dict)
            # Loop through individual dates
            for item in a_list:
                i = a_dict[item]
                if i is not None:
                    cnt += i
        count['pageviews'] += cnt
        stats['quality'] = 3 * points('categories_cnt') + \
                           4 * points('images_cnt') + \
                           4 * points('langlinks_cnt') + \
                           1 * points('links_cnt') + \
                           1 * points('linkshere_cnt') + \
                           2 * points('extlinks_cnt') + \
                           3 * points('redirects_cnt') + \
                           1 * points('contributors_tot')

        stats['pageviews_tot'] = str(count['pageviews'])
        if "(sv)" in p:
            stats['pageviews_sv'] = str(count['pageviews'])
            stats['len_sv'] = d['pages'][p]['length']
            lang_stats['sv'] = copy.deepcopy(stats)
        elif "(fi)" in p:
            stats['pageviews_fi'] = str(count['pageviews'])
            stats['len_fi'] = d['pages'][p]['length']
            lang_stats['fi'] = copy.deepcopy(stats)


def analyse_langstats(d, e):
    """"Analyze language data for all pages.

    Analyze language data for all pages. Links stats from pages in other languages together
     with same page in main language."""
    languages = d['stats']['languages'].split("|")
    for p in d['pages']:
        d['pages'][p]['stats']['total_langs'] = len(d['pages'][p]['langlinks'])
        for l_item in d['pages'][p]['langlinks']:
            l = list(l_item)[0]
            l_title = l_item[l]
            # -print(f"p {p} l {l} title {l_title}") TODO: proper logging
            if l in languages:
                # l_title = d['pages'][p]['langlinks'][l]
                p_in_lang = f"{l_title} ({l})"
                # -print(f"l {l} title {l_title} p {p_in_lang} ")
                if p_in_lang in d['pages']:
                    pv_in_lang = d['pages'][p_in_lang]['stats']['pageviews_tot']
                    l_in_lang = d['pages'][p_in_lang].get('length', -1)
                    # -print(f"p {p} pv {pv_in_lang} l {l_in_lang}")
                    d['pages'][p]['stats']["pageviews_" + l] = pv_in_lang
                    d['pages'][p]['stats']["len_" + l] = l_in_lang
                    d['pages'][p]["lang_stats"][l] = copy.deepcopy(d['pages'][p_in_lang]['stats'])


def analyse_time_interval(d, e):
    """Add information about pageview data to main 'stats' dict.

    Analyze pageview data and add start date, end date, and duration in days to main 'stats' part of dict."""
    first = "2099-12-13"
    last = "1899-01-01"
    for p in d['pages']:
        page = d['pages'][p]
        if 'pageviews' in page:
            for a_date in page['pageviews']:
                first = min(first, a_date)
                last = max(last, a_date)
    d['stats']['date_from'] = first
    d['stats']['date_to'] = last
    d['stats']['pv_days'] = days_between(first, last) + 1


def analyse_and_save_contributors(d, e, category, fmt='html'):
    """Analyze contributors and save list of top contributors in descending order.

    Analyze contributor data from all pages. Create list of all contributors
     ordered based onnumber of contributions.

     Format of saved file can be specified with :param fmt as either html or wikitext."""
    html = HTML()
    user_stat = {}
    l = list(d['pages'])
    c_title = c_item = 0
    for title in l:
        c_title += 1
        lang = title.split("(")[-1].strip(")")
        l2 = d['pages'][title]['contributors']
        for item in l2:
            c_item += 1
            if item in user_stat:
                user_stat[item]['edits'] += 1
            else:
                user_stat[item] = {}
                user_stat[item]['edits'] = 1
            if lang in user_stat[item]:
                user_stat[item][lang] += 1
            else:
                user_stat[item][lang] = 1
    c_contrib = len(user_stat)
    if len(user_stat) > 1000:
        user_stat = {k: v for k, v in user_stat.items() if v['edits'] > 5}
    langs = d['stats']['languages'].split("|")
    def comparer(left, right):
        for lang_column in langs:
            l = user_stat[left].get(lang_column, 0)
            r = user_stat[right].get(lang_column, 0)
            t =  r - l
            if t:
                return t
        return 0
    user_sorted = sorted(user_stat, key=cmp_to_key(comparer))

    stats = d['stats']
    page_title = stats['category_title']
    page_title = f"{page_title}: {c_contrib} wikipedianer, {c_title} artiklar, {c_item} w x a"
    datum = d['stats']['scrape_start'][:10]
    date_from = stats['date_from']
    date_to = stats['date_to']
    desc = f"Användarstatistik för tidsperioden {date_from}--{date_to}, körd {datum}"

    if fmt == 'html':
        html.set_title_desc(page_title, desc)
        h = html.doc_header()
        h += html.start_table(column_count=3)
        h += th("Nr") + thl("Wikipedian")
        for lang in langs:
            h += th(lang)
        h = tr(h)

    elif fmt == 'wikitext':
        h = f"= {page_title} = \n\n\n{desc}\n\n\n"
        h1 = ['Nr', 'Wikipedian']
        for lang in langs:
            h1.append(lang)
        h += table_start(h1, [])

    else:
        print("Unknown file format, try html instead")
        h = ""

    i = 0
    for user in user_sorted:
        i += 1

        user_page = f"https://sv.wikipedia.org/wiki/Användare:{user}"
        disc_page = f"https://sv.wikipedia.org/wiki/Användardiskussion:{user}"

        if fmt == 'html':
            a_href = "<a href='{}'>{}</a>"

            row = tdr(a_href.format(disc_page, i))
            row += td(a_href.format(user_page, user))
            for lang in langs:
                contrib_page = f"https://{lang}.wikipedia.org/wiki/Special:Contributions/{user}"
                row += tdr(a_href.format(contrib_page, user_stat[user].get(lang, 0)))

            h += tr(row)

        elif fmt == 'wikitext':
            a_href = "[{} {}]"
            row = align(a_href.format(disc_page.replace(' ', '&nbsp;'), i))
            row += cell(a_href.format(user_page.replace(' ', '&nbsp;'), user))
            for lang in langs:
                contrib_page = f"https://{lang}.wikipedia.org/wiki/Special:Contributions/{user}"
                row += align(a_href.format(contrib_page.replace(' ', '&nbsp;'), user_stat[user].get(lang, 0)))

            h += f"{row}|-\n"

    if fmt == 'html':
        h += html.end_table()
        h += html.doc_footer()

        dir_date = d['stats']['scrape_start'][:10]
        save_utf_file(f"contrib_{category}.html", "html", h, dir_date=dir_date)

    elif fmt == 'wikitext':
        h += "|}\n"

        dir_date = d['stats']['scrape_start'][:10]
        save_utf_file(f"contrib_{category}.txt", "wikitext", h, dir_date=dir_date)


def save_as_html(d, e, api_fields, category):
    """Create html table of category and save as html file."""
    html = HTML()
    try:
        analyse_pagestats(d, e, api_fields)
        analyse_time_interval(d, e)
        analyse_langstats(d, e)
    except KeyError as ke:
        e['error_analyze'] = {'info': ke.args, }
        print(f'Cound not analyze, the pages are missing data, canceling...')
        return

    stats = d['stats']
    page_title = stats['category_title']
    datum = stats['scraped'][:-3]
    date_from = stats['date_from']
    date_to = stats['date_to']
    date_days = stats['pv_days']

    desc = f"Sidvisningsstatistik {datum} för tidsperioden {date_from}--{date_to} ({date_days} dagar)"

    html.set_title_desc(page_title, desc)
    h = html.doc_header()
    h += html.start_table(column_count=13)

    subh1 = th("") + th("") + th("Svenska", 5) + th("Finska", 2)
    subh1 += th("Engelska", 2) + th("Tyska", 2)
    subh1 = tr(subh1)
    subh_grupp = th("Visat") + th(u"Längd")
    subh2 = th("Nr") + thl("Artikel")
    subh2 += th("Visat") + th("% av fi") + th(u"Längd") + th("% av fi") + th("Kvalitet")
    subh2 += subh_grupp * 3
    subh2 += th("Språk(Totalt)")
    subh2 = tr(subh2)

    l_categories = list(d['categories'])
    l_categories.sort(key=lambda x: d['categories'][x]['order'])
    i_cat = 0
    for title in l_categories:
        i_cat += 1
        pages = d['categories'][title]['pages']
        pl = []
        for p in pages:
            if "sv" in p:
                weight = (int(d['pages'][p]['stats'].get('pageviews_sv', 0)) + 1) * 100000
            elif "fi" in p:
                # removes duplicates with finnish names from list
                other_langs = {}
                for item in d['pages'][p]['langlinks']:
                    other_langs.update(item)
                if 'sv' in other_langs and f"{other_langs['sv']} (sv)" in d['pages']:
                    continue
                else:
                    weight = int(d['pages'][p]['stats'].get('pageviews_fi', 0))
            else:
                print(f"Page {p} does not exist in sv or fi! Oh no!")
                weight = 0
            # print("weight %s" % weight)

            d['categories'][title]['pages'][p]['order'] = weight
            pl.append({'title': p, 'weight': weight})
        # -print("pl ----")
        # -pprint(pl)

        # skip empty categories
        if not pl:
            i_cat -= 1
            continue

        pl.sort(key=lambda x: x['weight'], reverse=True)
        cls = ""
        if '(sv)' not in title:
            cls = 'red'
        h += html.h2(f"{i_cat}. {title}", cls=cls)
        h += subh1
        h += subh2
        i_p = 0
        for p_item in pl:
            i_p += 1
            p = p_item['title']
            if p not in d['pages']:
                continue
            the_page = d['pages'][p]
            stats = d['pages'][p]['stats']
            short_title = the_page['title']
            quality = stats['quality']
            total_langs = int(stats['total_langs']) + 1

            pv_sv = int(stats.get('pageviews_sv', 0))
            pv_fi = int(stats.get('pageviews_fi', 0))
            pv_en = int(stats.get('pageviews_en', 0))
            pv_de = int(stats.get('pageviews_de', 0))

            l_sv = int(stats.get('len_sv', 0))
            l_fi = int(stats.get('len_fi', 0))
            l_en = int(stats.get('len_en', 0))
            l_de = int(stats.get('len_de', 0))

            # % of sv length in relation to fi
            pct_l = 0 if l_fi == 0 else 100 * l_sv / l_fi
            sp_l = "*" if l_fi == 0 else f'{pct_l:.0f}' + "%"
            sp_l = red(sp_l) if pct_l < 70 else sp_l
            sp_l = bold(sp_l) if pct_l < 30 else sp_l
            sp_l = "" if l_sv == 0 else sp_l

            # % of sv pageviews in relation to fi
            pct_pv = 0 if pv_fi == 0 else 100 * pv_sv / pv_fi
            sp_pv = "*" if pv_fi == 0 else f'{pct_pv:.0f}' + "%"
            sp_pv = red(sp_pv) if pct_pv < 40 else sp_pv
            sp_pv = bold(sp_pv) if pct_pv < 10 else sp_pv
            sp_pv = "" if l_sv == 0 else sp_pv

            s_pv = "" if pv_sv == 0 else str(pv_sv)
            s_length = "-" if l_sv == 0 else str(l_sv)
            si_p = red(str(i_p)) if l_sv == 0 else str(i_p)

            p_fi = p_en = p_de = ""
            if 'langlinks' in d['pages'][p]:
                ll = d['pages'][p]['langlinks']
                for item in ll:
                    lang = list(item)[0]
                    if lang == 'fi':
                        p_fi = item['fi']
                    if lang == 'en':
                        p_en = item['en']
                    if lang == 'de':
                        p_de = item['de']
            url_s = "<a href='https://{}.wikipedia.org/wiki/{}'>{}</a>"
            url_lang = "fi" if l_sv == 0 else "sv"
            url_title = url_s.format(url_lang, short_title, short_title)
            url_title = italic(url_title) if l_sv == 0 else url_title

            url_fi = "-" if p_fi == "" else url_s.format('fi', p_fi, pv_fi)
            url_en = "-" if p_en == "" else url_s.format('en', p_en, pv_en)
            url_de = "-" if p_de == "" else url_s.format('de', p_de, pv_de)

            if p_fi == "":
                l_fi = "-"
            if p_en == "":
                l_en = "-"
            if p_de == "":
                l_de = "-"

            row = tdr(si_p) + td(url_title) + tdr(s_pv) + tdr(sp_pv)
            row += tdr(s_length) + tdr(sp_l) + tdr(quality)
            row += tdr(url_fi) + tdr(l_fi)
            row += tdr(url_en) + tdr(l_en)
            row += tdr(url_de) + tdr(l_de)
            row += tdr(total_langs)
            h += tr(row)
    h += html.end_table()
    h += html.doc_footer()

    dir_date = d['stats']['scrape_start'][:10]
    save_utf_file(f"c_{category}.html", "html", h, dir_date=dir_date)

def save_as_csv(d, e, api_fields, category, need_analyse=False):
    """Create csv table of category and save as csv file."""
    if need_analyse:
        html = HTML()
        try:
            analyse_pagestats(d, e, api_fields)
            analyse_time_interval(d, e)
            analyse_langstats(d, e)
        except KeyError as ke:
            e['error_analyze'] = {'info': ke.args, }
            print('Cound not analyze, the pages are missing data, canceling...')
            return

    stats = d['stats']
    page_title = stats['category_title']
    datum = stats['scraped'][:-3]
    date_from = stats['date_from']
    date_to = stats['date_to']
    date_days = stats['pv_days']

    dir_date = d['stats']['scrape_start'][:10]
    filename = f"c_{category}_{date_from}--{date_to}_{date_days}.csv"
    with get_utf_file(filename, "csv", dir_date=dir_date) as f:
        w = csv.writer(f, delimiter=';')

        subh1 = [""] * 2 + ["Svenska"] + [""] * 4 + ["Finska", "", "Engelska", \
                 "", "Tyska"] + [""] * 2 + ["Svenska"] + [""] * 7 +            \
                 ["Finska"] + [""] * 7 + ["Engelska"] + [""] * 7 + ["Tyska"] + \
                 [""] * 7
        subh2 = ["Nr", "Artikel", "Visat", "% av fi", u"Längd", "% av fi",     \
                 "Kvalitet", "Visat", u"Längd", "Visat", u"Längd", "Visat",    \
                 u"Längd", "Språk(Totalt)"] + ["Kategorier", "Bilder",         \
                 "Länkar till WP", "Länkar från WP", "Länkar ut", "Aliasar",   \
                 "Redaktörer", "Editeringa"] * 4

        l_categories = list(d['categories'])
        l_categories.sort(key=lambda x: d['categories'][x]['order'])
        i_cat = 0
        for title in l_categories:
            i_cat += 1
            pages = d['categories'][title]['pages']
            pl = []
            for p in pages:
                if "sv" in p:
                    pstats = d['pages'][p]['stats']
                    weight = (int(pstats.get('pageviews_sv', 0)) + 1) * 100000
                elif "fi" in p:
                    # removes duplicates with finnish names from list
                    other_langs = {}
                    for item in d['pages'][p]['langlinks']:
                        other_langs.update(item)
                    if 'sv' in other_langs and \
                       f"{other_langs['sv']} (sv)" in d['pages']:
                        continue
                    else:
                        pstats = d['pages'][p]['stats']
                        weight = int(pstats.get('pageviews_fi', 0))
                else:
                    print(f"Page {p} does not exist in sv or fi! Oh no!")
                    weight = 0
                # print("weight %s" % weight)

                d['categories'][title]['pages'][p]['order'] = weight
                pl.append({'title': p, 'weight': weight})
            # -print("pl ----")
            # -pprint(pl)

            # skip empty categories
            if not pl:
                i_cat -= 1
                continue

            pl.sort(key=lambda x: x['weight'], reverse=True)
            w.writerow([f"{i_cat}.", f"{title}"] + [""] * 44)
            w.writerow(subh1)
            w.writerow(subh2)
            i_p = 0
            for p_item in pl:
                i_p += 1
                p = p_item['title']
                if p not in d['pages']:
                    continue
                the_page = d['pages'][p]
                stats = d['pages'][p]['stats']
                lang_stats = d['pages'][p]['lang_stats']
                short_title = the_page['title']
                quality = stats['quality']
                total_langs = int(stats['total_langs']) + 1

                pv_sv = int(stats.get('pageviews_sv', 0))
                pv_fi = int(stats.get('pageviews_fi', 0))
                pv_en = int(stats.get('pageviews_en', 0))
                pv_de = int(stats.get('pageviews_de', 0))

                l_sv = int(stats.get('len_sv', 0))
                l_fi = int(stats.get('len_fi', 0))
                l_en = int(stats.get('len_en', 0))
                l_de = int(stats.get('len_de', 0))

                sv_stats = lang_stats.get('sv', {})
                categories_sv = int(sv_stats.get('categories_cnt', 0))
                images_sv = int(sv_stats.get('images_cnt', 0))
                links_sv = int(sv_stats.get('links_cnt', 0))
                linkshere_sv = int(sv_stats.get('linkshere_cnt', 0))
                extlinks_sv = int(sv_stats.get('extlinks_cnt', 0))
                redirects_sv = int(sv_stats.get('redirects_cnt', 0))
                contributors_sv = int(sv_stats.get('contributors_cnt', 0))
                revisions_cnt_sv = int(sv_stats.get('revisions_cnt', 0))

                fi_stats = lang_stats.get('fi', {})
                categories_fi = int(fi_stats.get('categories_cnt', 0))
                images_fi = int(fi_stats.get('images_cnt', 0))
                links_fi = int(fi_stats.get('links_cnt', 0))
                linkshere_fi = int(fi_stats.get('linkshere_cnt', 0))
                extlinks_fi = int(fi_stats.get('extlinks_cnt', 0))
                redirects_fi = int(fi_stats.get('redirects_cnt', 0))
                contributors_fi = int(fi_stats.get('contributors_cnt', 0))
                revisions_cnt_fi = int(fi_stats.get('revisions_cnt', 0))

                en_stats = lang_stats.get('en', {})
                categories_en = int(en_stats.get('categories_cnt', 0))
                images_en = int(en_stats.get('images_cnt', 0))
                links_en = int(en_stats.get('links_cnt', 0))
                linkshere_en = int(en_stats.get('linkshere_cnt', 0))
                extlinks_en = int(en_stats.get('extlinks_cnt', 0))
                redirects_en = int(en_stats.get('redirects_cnt', 0))
                contributors_en = int(en_stats.get('contributors_cnt', 0))
                revisions_cnt_en = int(en_stats.get('revisions_cnt', 0))

                de_stats = lang_stats.get('de', {})
                categories_de = int(de_stats.get('categories_cnt', 0))
                images_de = int(de_stats.get('images_cnt', 0))
                links_de = int(de_stats.get('links_cnt', 0))
                linkshere_de = int(de_stats.get('linkshere_cnt', 0))
                extlinks_de = int(de_stats.get('extlinks_cnt', 0))
                redirects_de = int(de_stats.get('redirects_cnt', 0))
                contributors_de = int(de_stats.get('contributors_cnt', 0))
                revisions_cnt_de = int(de_stats.get('revisions_cnt', 0))

                # % of sv length in relation to fi
                pct_l = 0 if l_fi == 0 else 100 * l_sv / l_fi
                sp_l = "*" if l_fi == 0 else f'{pct_l:.0f}' + "%"
                sp_l = "" if l_sv == 0 else str(sp_l)

                # % of sv pageviews in relation to fi
                pct_pv = 0 if pv_fi == 0 else 100 * pv_sv / pv_fi
                sp_pv = "*" if pv_fi == 0 else f'{pct_pv:.0f}' + "%"
                sp_pv = "" if l_sv == 0 else str(sp_pv)

                s_pv = "" if pv_sv == 0 else str(pv_sv)
                s_length = "-" if l_sv == 0 else str(l_sv)

                p_fi = p_en = p_de = ""
                if 'langlinks' in d['pages'][p]:
                    ll = d['pages'][p]['langlinks']
                    for item in ll:
                        lang = list(item)[0]
                        if lang == 'fi':
                            p_fi = item['fi']
                        if lang == 'en':
                            p_en = item['en']
                        if lang == 'de':
                            p_de = item['de']

                url_fi = "-" if p_fi == "" else str(pv_fi)
                url_en = "-" if p_en == "" else str(pv_en)
                url_de = "-" if p_de == "" else str(pv_de)

                if p_fi == "":
                    l_fi = "-"
                if p_en == "":
                    l_en = "-"
                if p_de == "":
                    l_de = "-"

                w.writerow([i_p, short_title, s_pv, sp_pv, s_length, sp_l,     \
                            quality, url_fi, l_fi, url_en, l_en, url_de, l_de, \
                            total_langs, categories_sv, images_sv,             \
                            links_sv, linkshere_sv, extlinks_sv, redirects_sv, \
                            contributors_sv, revisions_cnt_sv, categories_fi,  \
                            images_fi, links_fi, linkshere_fi, extlinks_fi,    \
                            redirects_fi, contributors_fi, revisions_cnt_fi,   \
                            categories_en, images_en, links_en, linkshere_en,  \
                            extlinks_en, redirects_en, contributors_en,        \
                            revisions_cnt_en, categories_de, images_de,        \
                            links_de, linkshere_de, extlinks_de, redirects_de, \
                            contributors_de, revisions_cnt_de])
        print(f"Skapade csv-filen {filename} ({f.tell()} tecken)")


def save_as_html_lang(d, e, api_fields, category):
    """Create html table with listing lengths of pages in all available languages and save as html file."""
    html = HTML()
    # try:
    analyse_pagestats(d, e, api_fields)
    analyse_time_interval(d, e)
    analyse_langstats(d, e)
    # except KeyError as ke:
    #     e['error_analyze'] = {'info': ke.args, }
    #     print(f'Kunde inte analysera, det fattas data från sidorna! Avbryter...')
    #     return

    stats = d['stats']
    page_title = stats['category_title'].strip(".txt")
    datum = stats['scraped'][:-3]
    date_from = stats['date_from']
    date_to = stats['date_to']
    date_days = stats['pv_days']

    desc = f"Wikipedia Page View Stats {datum} for the period {date_from}--{date_to} ({date_days} days)"

    html.set_title_desc(page_title, desc)
    h = html.doc_header()

    # identify total count of all languages
    langs = {}
    pages = d['pages']
    for p in pages:
        lang = p.split("(")[-1].strip(")")
        # language is at end, eg. (de), but the page title itself may contain parentheses
        #  that do not refer to language - skip those!
        is_a_lang = len(lang) < 4 or lang == "simple"
        if not is_a_lang:
            continue
        if lang not in langs:
            langs[lang] = 0
        pageviews = pages[p].get('pageviews', [])
        for pv_date in pageviews:
            pv = pageviews[pv_date]
            if pv is not None:
                langs[lang] += pv
    print(f"languages, unsorted {langs}")
    h += html.start_table(column_count=13)

    subh1 = th("No") + thl("Article")
    for l in langs:
        subh1 += th(l)
    subh1 = tr(subh1)

    l_categories = list(d['categories'])
    l_categories.sort(key=lambda x: d['categories'][x]['order'])
    i_cat = 0
    for title in l_categories:
        print(f"Overall title {title}")
        i_cat += 1
        pages = d['categories'][title]['pages']

        sorted_pages = {}
        for page in pages:
            if page not in d['pages']:
                continue
            sorted_pages[page] = d['pages'][page]
        def comparer(left, right):
            for lang_column in langs:
                l_stats = sorted_pages[left]['lang_stats'].get(lang_column, {})
                l = int(l_stats.get('pageviews_tot', 0))
                r_stats = sorted_pages[right]['lang_stats'].get(lang_column, {})
                r = int(r_stats.get('pageviews_tot', 0))
                t =  r - l
                if t:
                    return t
            return 0
        sorted_pages = sorted(sorted_pages, key=cmp_to_key(comparer))

        cls = ""
        h += html.h2(f"{i_cat}. {title}", cls=cls)
        h += subh1
        i_p = 0
        url_s = "<a href='https://{}.wikipedia.org/wiki/{}'>{}</a>"
        for page in sorted_pages:
            lang = page.split("(")[-1].strip(")")
            title = d['pages'][page]['title']
            pv = d['pages'][page]['stats']['pageviews_tot']
            url = url_s.format(lang, title, title)
            url_pv = url_s.format(lang, title, pv)
            lang_dict = {}
            for k in d['pages'][page]['langlinks']:
                lang_dict[list(k)[0]] = k[list(k)[0]]
            # print(f"== page = {page} title {title} dict {lang_dict}")
            i_p += 1
            row = tdr(i_p) + td(url)
            for lang_column in langs:
                if lang_column == lang:
                    row += tdr(url_pv)
                    continue
                cell = ""
                if 'langlinks' in d['pages'][page]:
                    has_lang = lang_column in lang_dict
                    if has_lang:
                        page_in_lang = lang_dict[lang_column] + " (" + lang_column + ")"
                        # print(page_in_lang + " -- " + lang_dict[lang_column])
                        if page_in_lang in d['pages']:
                            value = d['pages'][page_in_lang]['stats']['pageviews_tot']
                            lang_title = d['pages'][page_in_lang]['title']
                            cell = url_s.format(lang_column, lang_title, value)
                row += tdr(cell)
            h += tr(row)
    h += html.end_table()
    h += html.doc_footer()

    dir_date = d['stats']['scrape_start'][:10]
    save_utf_file(f"l_{category}.html", "html", h, dir_date=dir_date)


def save_as_html_graphic(d, e, api_fields, category):
    """Create html file with colored graphs comparing length and views between
    languages"""
    html = HTML()
    # try:
    analyse_pagestats(d, e, api_fields)
    analyse_time_interval(d, e)
    analyse_langstats(d, e)
    # except KeyError as ke:
    #     e['error_analyze'] = {'info': ke.args, }
    #     print(f'Kunde inte analysera, det fattas data från sidorna! Avbryter...')
    #     return

    stats = d['stats']
    page_title = stats['category_title'].strip(".txt")
    datum = stats['scraped'][:-3]
    date_from = stats['date_from']
    date_to = stats['date_to']
    date_days = stats['pv_days']

    desc = f"Wikipedia Page View Stats {datum} for the period {date_from}--{date_to} ({date_days} days)"

    html.set_title_desc(page_title, desc)
    h = html.doc_header()
    h += graph(graph_bar(html.h2("Svenska"), "sv", 1) +
               graph_bar(html.h2("Finska"), "fi", 1) +
               graph_bar(html.h2("Engelska"), "en", 1) +
               graph_bar(html.h2("Tyska"), "de", 1),
              cls="legend")
    h += html.start_table(column_count=6)

    subh = (th("Artikel") + th("SV Längd") +
           th("Längd") + th("SV Läsningar") +
           th("Läsningar") + th("Förslag"))
    subh = tr(subh)

    l_categories = list(d['categories'])
    l_categories.sort(key=lambda x: d['categories'][x]['order'])
    i_cat = 0
    for title in l_categories:
        i_cat += 1
        pages = d['categories'][title]['pages']
        pl = []
        max_len = 0
        max_pageviews = 0
        for p in pages:
            if "sv" in p:
                weight = (int(d['pages'][p]['stats'].get('pageviews_sv', 0)) + 1) * 100000
            elif "fi" in p:
                # removes duplicates with finnish names from list
                other_langs = {}
                for item in d['pages'][p]['langlinks']:
                    other_langs.update(item)
                if 'sv' in other_langs and f"{other_langs['sv']} (sv)" in d['pages']:
                    continue
                else:
                    weight = int(d['pages'][p]['stats'].get('pageviews_fi', 0))
            else:
                print(f"Page {p} does not exist in sv or fi! Oh no!")
                weight = 0

            d['categories'][title]['pages'][p]['order'] = weight
            pl.append({'title': p, 'weight': weight})

        # skip empty categories
        if not pl:
            i_cat -= 1
            continue

        pl.sort(key=lambda x: x['weight'], reverse=True)
        cls = ""
        if '(sv)' not in title:
            cls = 'red'
        h += html.h2(f"{i_cat}. {title}", cls=cls)
        h += subh
        i_p = 0
        for p_item in pl:
            i_p += 1
            p = p_item['title']
            if p not in d['pages']:
                continue
            the_page = d['pages'][p]
            stats = d['pages'][p]['stats']
            short_title = the_page['title']
            quality = stats['quality']

            pv_sv = int(stats.get('pageviews_sv', 0))
            pv_fi = int(stats.get('pageviews_fi', 0))
            pv_en = int(stats.get('pageviews_en', 0))
            pv_de = int(stats.get('pageviews_de', 0))

            l_sv = int(stats.get('len_sv', 0))
            l_fi = int(stats.get('len_fi', 0))
            l_en = int(stats.get('len_en', 0))
            l_de = int(stats.get('len_de', 0))

            url_s = "<a href='https://{}.wikipedia.org/wiki/{}'>{}</a>"
            url_lang = "fi" if l_sv == 0 else "sv"
            url_title = url_s.format(url_lang, short_title, short_title)
            url_title = italic(url_title) if l_sv == 0 else url_title

            if max_len < l_sv:
                max_len = l_sv
            if max_pageviews < pv_sv:
                max_pageviews = pv_sv
            row = td(url_title, cls="row-title")
            relative_len_graph = graph(graph_bar(lang="sv", size=l_sv) +
                                       graph_bar(lang="fill", size=max_len - l_sv),
                                       cls="relative")
            row += td(relative_len_graph)
            len_graph = graph(graph_bar(lang="sv", size=l_sv) +
                              graph_bar(lang="fi", size=l_fi) +
                              graph_bar(lang="en", size=l_en) +
                              graph_bar(lang="de", size=l_de))
            row += td(len_graph)
            relative_pv_graph = graph(graph_bar(lang="sv", size=pv_sv) +
                                      graph_bar(lang="fill", size=max_pageviews - pv_sv),
                                      cls="relative")
            row += td(relative_pv_graph)
            pv_graph = graph(graph_bar(lang="sv", size=pv_sv) +
                             graph_bar(lang="fi", size=pv_fi) +
                             graph_bar(lang="en", size=pv_en) +
                             graph_bar(lang="de", size=pv_de))
            row += td(pv_graph)

            # Rules for attention boxes
            boxes = {}
            for lang_name, lang_len, lang_pv in [('sv', l_sv, pv_sv),
                                                 ('fi', l_fi, pv_fi),
                                                 ('en', l_en, pv_en),
                                                 ('de', l_de, pv_de)]:
                # 1. language under 10% of swedish
                if lang_len < l_sv * 0.1 and pv_sv > 5:
                    boxes[lang_name] = 1

                # 2. Read a lot but comparatively  short
                if lang_pv * 5 > lang_len and pv_sv > 5:
                    boxes[lang_name] = 2

                # 3. language missing totally
                if lang_len == 0 and (pv_sv > 5 or lang_name == "sv"):
                    boxes[lang_name] = 3
                    # box_levels.append(3)
                    # box_langs.append(lang_name)

            boxes = sorted(boxes.items(), key=lambda x: x[1])
            box_langs, box_levels = list(zip(*boxes)) if boxes else ([], [])
            row += td(action_box(box_levels, box_langs))
            h += tr(row)

    h += html.end_table()
    h += html.doc_footer()

    dir_date = d['stats']['scrape_start'][:10]
    save_utf_file(f"visual_{category}.html".replace(" ", "_"), "html", h, dir_date=dir_date)


def save_as_wikitext(d, e, api_fields, category, page_type='normal'):
    """Create table of all pages in category and save as wikitext markup file.

    Create table of all pages in category and save as textfile in wikitext markup. To be used in mediawiki."""
    try:
        analyse_pagestats(d, e, api_fields)
        analyse_time_interval(d, e)
        analyse_langstats(d, e)
    except KeyError as ke:
        e['error_analyze'] = {'info': ke.args, }
        print(f'Could not analyze, the pages are missing data')

    stats = d['stats']
    page_title = stats['category_title']
    other_langs = stats['languages'][3:].split('|')
    lang_names = {'sv': 'Svenska', 'fi': 'Finska', 'en': 'Engelska',
                  'de': 'Tyska', 'no': 'Norska', 'fr': 'Franska'}
    try:
        site = wiki.Wiki(f"https://sv.wikipedia.org/w/api.php")
        params = {'action': 'query', 'meta': 'languageinfo',
                  'liprop': 'name', 'uselang': 'sv'}
        req_links = api.APIRequest(site, params)
        for sub_result in req_links.queryGen():  # async_gen(req_links):
            for k, v in sub_result['query']['languageinfo'].items():
                lang_names[k] = v['name'].capitalize()
    except exceptions.APIError as we:
        e['error_analyze'] = {'info': we.args, }
        print('Failed to get language information from Wiki')
    datum = stats['scraped'][:-3]
    date_from = stats['date_from']
    date_to = stats['date_to']
    date_days = stats['pv_days']

    desc = f"Sidvisningsstatistik {datum} för tidsperioden {date_from}--{date_to} ({date_days} dagar)\n\n"
    contrib_link = f"[[{page_title}:Contributors|Contributors]]"
    top_link = f"[[top/{page_title}|Top 100 artiklar i kategorin]]"

    text = f"{desc}\n\n{contrib_link}\n\n{top_link}\n\n\n"
    if page_type == 'top100':
        text = f"{desc}\n\nVisar de 100 populäraste sidorna i kategorin samt i alla dess underkategorier.\n\n\n"
    h1 = [rowspan('Nr'), rowspan(colspan('Artikel', 3)), colspan('Svenska', 5)]
    lang_headers = []
    for l in other_langs:
        lang_headers += [colspan(lang_names.get(l, l))]
    h1 += lang_headers
    h1 = [h1[0]] + [align(h, 'center') for h in h1[1:]]

    h2 = ['Visat', '% av fi', 'Längd', '% av fi', 'Kvalitet'] + ['Visat', 'Längd'] * len(other_langs)
    h2.append('Språk (Totalt)')
    subh = table_start(h1, h2)

    l_categories = list(d['categories'])
    l_categories.sort(key=lambda x: d['categories'][x]['order'])
    i_cat = 0

    for cat in l_categories:
        i_cat += 1
        pages = []
        if page_type == 'normal':
            pages = d['categories'][cat]['pages']
        elif page_type == 'top100':
            pages = d['pages']
        pl = []
        for p in pages:
            if "sv" in p:
                weight = (int(d['pages'][p]['stats'].get('pageviews_sv', 0)) + 1) * 100000
            elif "fi" in p:
                # removes duplicates with finnish names from list
                other_lang_links = {}
                for item in d['pages'][p]['langlinks']:
                    other_lang_links.update(item)
                if 'sv' in other_lang_links and f"{other_lang_links['sv']} (sv)" in d['pages']:
                    continue
                else:
                    weight = int(d['pages'][p]['stats'].get('pageviews_fi', 0))
            else:
                print(f"Sidan {p} har varken sv eller fi! Oj nej!")
                weight = 0
            if page_type == 'normal':
                d['categories'][cat]['pages'][p]['order'] = weight
            pl.append({'title': p, 'weight': weight})
        # -print("pl ----")
        # -pprint(pl)

        # skip empty categories
        if not pl:
            i_cat -= 1
            continue

        pl.sort(key=lambda x: x['weight'], reverse=True)

        if page_type == 'top100':
            pl = [x for x in pl if x['weight'] != 0][:100]

        if '(sv)' not in cat:
            cat = f"<span style='color:red'>{cat}</span>"
        text += f'\n=    {i_cat} {cat} =\n\n'
        text += subh
        i_p = 0
        for p_item in pl:
            i_p += 1
            p = p_item['title']
            the_page = d['pages'][p]
            stats = d['pages'][p]['stats']
            short_title = the_page['title']
            quality = stats['quality']
            total_langs = int(stats['total_langs']) + 1
            final = {'pv': {}, 'len': {}, 'url': {}}

            for l in d['stats']['languages'].split('|'):
                final['pv'][l] = int(stats.get(f'pageviews_{l}', 0))
                final['len'][l] = int(stats.get(f"len_{l}", 0))
            l_sv = final['len']['sv']

            # % of sv length in relation to fi
            pct_l = 0 if final['len']['fi'] == 0 else 100 * l_sv / final['len']['fi']
            sp_l = "*" if final['len']['fi'] == 0 else f'{pct_l:.0f}' + "%"
            sp_l = w_red(sp_l) if pct_l < 70 else sp_l
            sp_l = w_bold(sp_l) if pct_l < 30 else sp_l
            sp_l = "" if l_sv == 0 else sp_l

            # % of sv pageviews in relation to fi
            pct_pv = 0 if final['pv']['fi'] == 0 else 100 * final['pv']['sv'] / final['pv']['fi']
            sp_pv = "*" if final['pv']['fi'] == 0 else f'{pct_pv:.0f}' + "%"
            sp_pv = w_red(sp_pv) if pct_pv < 40 else sp_pv
            sp_pv = w_bold(sp_pv) if pct_pv < 10 else sp_pv
            sp_pv = "" if l_sv == 0 else sp_pv

            s_pv = "" if final['pv']['sv'] == 0 else str(final['pv']['sv'])
            s_length = "-" if l_sv == 0 else str(l_sv)
            si_p = w_red(i_p) if l_sv == 0 else f"[[p/{short_title}|{i_p}]]"

            final['p'] = {l: "" for l in other_langs}
            if 'langlinks' in d['pages'][p]:
                ll = d['pages'][p]['langlinks']
                for item in ll:
                    lang = list(item)[0]
                    if lang in other_langs:
                        final['p'][lang] = item[lang].replace(' ', '&nbsp;')
            url_s = "[https://{}.wikipedia.org/wiki/{} {}]"
            url_lang = "fi" if l_sv == 0 else "sv"
            short_title = str(short_title).replace(' ', '&nbsp;')
            url_title = url_s.format(url_lang, short_title, short_title)
            url_title = w_italic(url_title) if l_sv == 0 else url_title

            for l in other_langs:
                if final['p'][l] == "":
                    final['url'][l] = "-"
                    final['len'][l] = "-"
                else:
                    final['url'][l] = url_s.format(l, str(final['p'][l]).replace(' ', '&nbsp;'), final['pv'][l])

            row = cell(si_p) + colspan(url_title, 3) + align(s_pv) + align(sp_pv)
            row += align(s_length) + align(sp_l) + align(quality)
            for l in other_langs:
                row += align(final['url'][l]) + align(final['len'][l])
            row += align(total_langs)
            row += "|-\n"
            text += row
        if page_type == 'top100':
            break
        text += "|}\n\n"

    dir_date = d['stats']['scrape_start'][:10]
    if page_type == 'normal':
        save_utf_file(f"c_{category}.txt", "wikitext", text, dir_date=dir_date)
    elif page_type == 'top100':
        save_utf_file(f"c_{category}_top100.txt", "wikitext", text, dir_date=dir_date)


def split_category(d, e, top_category):
    """Split all direct subcategories into own separate files.

    Split all direct subcategories into own separate files. Does not remove original main category file, only creates
    new files for all the subcategories.

    To be used for splitting up massive categories into smaller ones."""

    def copy_category(category, order):
        """Extract subcategory from main category.

        Extract subcategory from main category. Does not request new
        data from api, only partially copies data from existing file."""
        if category in cat['pages']:
            return
        cat['stats']['pages_cnt'] += 1
        cat['pages'][category] = d['pages'][category].copy()

        for p in d['categories'][category]['pages']:
            title = p
            if 'Kategori:' in title or 'Luokka:' in title or 'Category:' in title or 'Kategorie:' in title:
                cat['stats']['categories_cnt'] += 1
                cat['categories'][title] = d['categories'][title].copy()
                cat['categories'][title]['order'] = order
                copy_category(title, order + 1)
            cat['stats']['pages_cnt'] += 1
            cat['pages'][title] = d['pages'][title].copy()
            # checks for seconday language of pages
            if 'sv' in title:
                for l_page in cat['pages'][title]['langlinks']:
                    if list(l_page)[0] in d['stats']['languages'].split('|'):
                        l_lang, l_title = list(l_page.items())[0]
                        if '#' in l_title:
                            hashtag_index = l_title.index('#')
                            l_title = l_title[:hashtag_index]
                        full_title = f"{l_title} ({l_lang})"
                        cat['stats']['pages_cnt'] += 1
                        cat['pages'][full_title] = d['pages'][full_title].copy()

    # go through all subcaetegories, copy them, and save them in individual files
    cat = {'stats': {}, 'blacklist': {}, 'categories': {}, 'pages': {}}
    subcategories = [c for c in d['categories'][f"Kategori:{top_category} (sv)"]['pages'] if "Kategori:" in c]
    subcategories.remove(f"Kategori:{top_category} (sv)")
    for sub_cat in subcategories:
        short_title = sub_cat.split(':')[1][:-5]
        dashes = 50 - len(short_title)
        print(f"\n---------------New category: {short_title}{'-' * dashes}")
        # copy over base stats
        cat['stats']['category_title'] = short_title
        cat['stats']['languages'] = d['stats']['languages']
        cat['stats']['date_from'] = d['stats']['date_from']
        cat['stats']['date_to'] = d['stats']['date_to']
        cat['stats']['lang_1'] = d['stats']['lang_1']
        cat['stats']['lang_2'] = d['stats']['lang_2']
        cat['stats']['categories_cnt'] = 0
        cat['stats']['pv_days'] = d['stats']['pv_days']
        cat['stats']['response_time'] = -1
        cat['stats']['pages_cnt'] = 0
        cat['stats']['scrape_start'] = d['stats']['scrape_start']
        cat['stats']['scraped'] = d['stats']['scraped']

        # copy pages recusrively
        copy_category(sub_cat, 1)

        # check secondary language categories
        second_lang_title = ""
        if 'langlinks' in d['pages'][sub_cat]:
            for l in d['pages'][sub_cat]['langlinks']:
                lang = list(l)[0]
                if lang == d['stats']['lang_2']:
                    second_lang_title = f"{l[lang]} ({lang})"
                    break
            if second_lang_title != "":
                order = cat['stats']['categories_cnt']
                copy_category(second_lang_title, order + 1)

        # save files and reset dict
        dir_date = cat['stats']['scrape_start'][:10]
        json_file = f"{cat['stats']['category_title']}.json".replace(' ', '_')
        save_json_file(json_file, cat, dir_date=dir_date)
        cat = {'stats': {}, 'blacklist': {}, 'categories': {}, 'pages': {}}


def publish(d, e, api_fields, category, subpages=True):
    """Connect to mediawiki site and publish data about category.

    Connect to mediawiki site, log in and publish category file to a page. Will publish main category page under
    https://www.exampleUrl.com/CategoryName, separate stats page for each page in the category under
    URL/P/PageName, contributor list for category under URL/CategoryName:Contributors, and a list of the top 100
    pages in the category under URL/top/CategoryName.

    Enviroment variables can be used for site name and login credentails to support running the scrpt automatically."""

    # setup site and login, try to use env variables, otherwise ask user
    site = wiki.Wiki()
    if 'WIKISITE' not in os.environ:
        sitename = input("Wiki site url:")
        site = wiki.Wiki(sitename)
    else:
        site = wiki.Wiki(os.environ['WIKISITE'])
    if 'WIKIUSER' not in os.environ or 'WIKIPASSWORD' not in os.environ:
        # site = wiki.Wiki("https://projektfredrika.fi/api.php")
        user = input("Login name:")
        site.login(user)
    else:
        site.login(os.environ['WIKIUSER'], os.environ['WIKIPASSWORD'])

    # Ananlyze and crate files to upload
    save_as_wikitext(d, e, api_fields, category)
    analyse_and_save_contributors(d, e, category, fmt="wikitext")
    save_as_wikitext(d, e, api_fields, category, page_type='top100')

    # Locate newly created files
    wikitext_file = Path(f"wikitext")
    wikitext_file = list(wikitext_file.glob(f'*/c_{category}.txt'))
    wikitext_file.sort(reverse=True)
    wikitext_file_exists = False
    if wikitext_file:
        wikitext_file = wikitext_file[0]
        wikitext_file_exists = True
    if not wikitext_file_exists:
        print("Kunde inte hitta textfilen, finns kategorin alls?")
        return
    with open(str(wikitext_file), "r") as textfile:
        text = ''.join(textfile.readlines())

    wikitext_contrib_file = Path(f"wikitext")
    wikitext_contrib_file = list(wikitext_contrib_file.glob(f'*/contrib_{category}.txt'))
    wikitext_contrib_file.sort(reverse=True)
    wikitext_contrib_file_exists = False
    if wikitext_contrib_file:
        wikitext_contrib_file = wikitext_contrib_file[0]
        wikitext_contrib_file_exists = True
    if not wikitext_contrib_file_exists:
        print("Kunde inte hitta contrib textfilen, finns kategorin alls?")
        return
    with open(str(wikitext_contrib_file)) as textfile:
        contrib_text = ''.join(textfile.readlines())

    top100_file = Path(f"wikitext")
    top100_file = list(top100_file.glob(f'*/c_{category}_top100.txt'))
    top100_file.sort(reverse=True)
    top100_file_exists = False
    if top100_file:
        top100_file = top100_file[0]
        top100_file_exists = True
    if not top100_file_exists:
        print("Kunde inte hitta textfilen, finns kategorin alls?")
        return
    with open(str(top100_file), "r") as textfile:
        top100_text = ''.join(textfile.readlines())
    summary = f"Uppladdat med fredrikas Lupp med data från: {d['stats']['scraped']}"

    # setup the page and push the edits
    category_page = page.Page(site, category)
    editprop = {'text': text, 'bot': True, 'skipmd5': True, 'minor': category_page.exists, 'summary': summary}
    try:
        res = category_page.edit(**editprop)
    except exceptions.APIQueryError as ae:
        e['site_edit_error'] = {'info': ae.args}
        print(f"Fel med publiceringen av sidan på grund av: {ae.args}")
        res = {}
    contrib_page = page.Page(site, f"{category}:Contributors")
    editprop = {'text': contrib_text, 'bot': True, 'skipmd5': True, 'minor': contrib_page.exists, 'summary': summary}
    try:
        res_contrib = contrib_page.edit(**editprop)
    except exceptions.APIQueryError as ae:
        e['site_edit_error'] = {'info': ae.args}
        print(f"Fel med publiceringen av sidan på grund av: {ae.args}")
        res_contrib = {}
    top100_page = page.Page(site, f"top/{category}")
    editprop = {'text': top100_text, 'bot': True, 'skipmd5': True, 'minor': top100_page.exists, 'summary': summary}
    try:
        top_res = top100_page.edit(**editprop)
    except exceptions.APIQueryError as ae:
        e['site_edit_error'] = {'info': ae.args}
        print(f"Fel med publiceringen av sidan på grund av: {ae.args}")
        top_res = {}

    page_success = 'edit' in res and res['edit']['result'] == 'Success'
    contrib_success = 'edit' in res_contrib and res_contrib['edit']['result'] == 'Success'
    top_success = 'edit' in top_res and top_res['edit']['result'] == 'Success'
    if page_success and contrib_success and top_success:
        print(f"Lade upp filen för {category} på www.projektfredrika.fi/{category}")
        print(f"Lade upp filen för {category} contributors på www.projektfredrika.fi/{category}:Contributors")
        print(f"Lade upp filen för {category} top 100 på www.projektfredrika.fi/{category}:top")
    else:
        print("Uppladdningen misslyckades")
        return

    if not subpages:
        return

    # Publish all stat pages
    for p in d['pages']:
        title = d['pages'][p]['title']
        if '(sv)' not in p:
            continue
        page_site = page.Page(site, f"p/{title}")
        text = wikitext_page(d, e, p)
        editprop = {'text': text, 'bot': True, 'skipmd5': True, 'minor': category_page.exists, 'summary': summary}
        try:
            res = page_site.edit(**editprop)
            if 'edit' in res and res['edit']['result'] == 'Success':
                print(f"Lade upp sidan p/{title}")
        except exceptions.APIQueryError as ae:
            e['site_edit_error'] = {'info': ae.args}
            print(f"Fel med publiceringen av sidan p/{title} på grund av: {ae.args}")


def wikitext_page(d, e, title, fmt='wikitext'):
    """Create infobox with stats about a single page from a category.

    Create infobox with stats about a single page from a category. Currently only supports formatting as wikitext.
    Only returns the string of the text, does not save any files or modify other data structures."""
    datum = d['stats']['scrape_start'][:10]
    date_from = d['stats']['date_from']
    date_to = d['stats']['date_to']
    date_days = d['stats']['pv_days']

    desc = f"Sidvisningsstatistik {datum} för tidsperioden {date_from}--{date_to} ({date_days} dagar)\n\n"

    page_stats = d['pages'][title]['stats']
    if fmt == 'wikitext':
        text = f"{desc}\n\n\n"

        table = table_start([colspan('Sidinformation')], [], cellpadding=3, cls='wikitable')
        table += f"|Visningar || align='right' | {page_stats['pageviews_sv']}\n|-\n"
        table += f"|Längd || align='right' | {page_stats['len_sv']}\n|-\n"
        table += f"|Kvalitet || align='right' | {page_stats['quality']}\n|-\n"
        if 'len_fi' in page_stats:
            table += f"|Visningar Finska || align='right' | {page_stats['pageviews_fi']}\n|-\n"
            table += f"|Längd Finska || align='right' | {page_stats['len_fi']}\n|-\n"
        if 'len_en' in page_stats:
            table += f"|Visningar Engelska || align='right' | {page_stats['pageviews_en']}\n|-\n"
            table += f"|Längd Engelska || align='right' | {page_stats['len_en']}\n|-\n"
        if 'len_de' in page_stats:
            table += f"|Visningar Tyska || align='right' | {page_stats['pageviews_de']}\n|-\n"
            table += f"|Längd Tyska || align='right' | {page_stats['len_de']}\n|-\n"

        table += f"|Kategorier || align='right' | {page_stats['categories_cnt']}\n|-\n"
        table += f"|Kontributörer || align='right' | {page_stats['contributors_tot']}\n|-\n"
        table += f"|Antal andra språk || align='right' | {page_stats['langlinks_cnt']}\n|-\n"
        table += f"|Externa länkar || align='right' | {page_stats['extlinks_cnt']}\n|-\n"
        table += f"|Bilder || align='right' | {page_stats['images_cnt']}\n|-\n"
        table += f"|Länkar || align='right' | {page_stats['links_cnt']}\n|-\n"
        table += f"|Omdirigeringar || align='right' | {page_stats['redirects_cnt']}\n|-\n"
        table += f"|Länkar till denna sida || align='right' | {page_stats['linkshere_cnt']}\n|-\n"

        table += "|}\n\n"
        text += table
        text += """Kvalitet räknas ut med formeln: 
        Kvalitet = 
        3 * antalet kategorier + 
        4 * antalet bilder + 
        4 * antalet andra språk + 
        1 * antalet länkar + 
        1 * antalet länkar till denna sida +
        2 * externa länkar + 
        3 * antalet omdirigeringar +
        1 * antalet kontributörer
        """
        return text

    elif fmt == 'print':
        text = f"Visningar---------------{page_stats['pageviews_sv']}\n"
        text += f"Längd-------------------{page_stats['len_sv']}\n"
        text += f"Kvalitet----------------{page_stats['quality']}\n"
        if 'len_fi' in page_stats:
            text += f"Visningar Finska--------{page_stats['pageviews_fi']}\n"
            text += f"Längd Finska------------{page_stats['len_fi']}\n"
        if 'len_en' in page_stats:
            text += f"Visningar Engelska------{page_stats['pageviews_en']}\n"
            text += f"Längd Engelska----------{page_stats['len_en']}\n"
        if 'len_de' in page_stats:
            text += f"Visningar Tyska---------{page_stats['pageviews_de']}\n"
            text += f"Längd Tyska-------------{page_stats['len_de']}\n"
        text += f"Kategorier--------------{page_stats['categories_cnt']}\n"
        text += f"Kontributörer-----------{page_stats['contributors_tot']}\n"
        text += f"Antal andra språk-------{page_stats['langlinks_cnt']}\n"
        text += f"Externa länkar----------{page_stats['extlinks_cnt']}\n"
        text += f"Bilder------------------{page_stats['images_cnt']}\n"
        text += f"Länkar------------------{page_stats['links_cnt']}\n"
        text += f"Omdirigeringar----------{page_stats['redirects_cnt']}\n"
        text += f"Länkar till denna sida--{page_stats['linkshere_cnt']}\n"
        return text
