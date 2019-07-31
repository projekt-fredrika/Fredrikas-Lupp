#! /usr/bin/env python3
# coding: utf-8
"""
Scripts for creating a list of coordinates and info for
all pages in a wikipedia category.

Currently takes to constants:
    CATEGORY_TITLE - what category from wikipedia to scrape
    WIKI_LANG - which language wikipedia to query from
    INFOBOX_FILEDS - what fileds to save from the infobox on each page

The results are saved as a csv file.
"""

import time
import csv
from wikitools import wiki, api
import requests

CATEGORY_TITLE = 'Öar i Pargas'
WIKI_LANG = 'sv'
INFOBOX_FILEDS = ['name', 'area', 'length', 'length_orientation',
                  'municipality', 'district']


def get_cords(titles):
    """Get coordinates for titles via mediawiki API."""

    par = {'action': 'query', 'titles': titles,
           'prop': 'coordinates', 'colimit': 500, 'format': 'json'}
    p_req = api.APIRequest(site, par)
    for resp in p_req.queryGen():
        for t, page in resp['query']['pages'].items():
            if 'coordinates' in page:
                print(f"{page['title']} --- N {page['coordinates'][0]['lat']}"
                      f", E {page['coordinates'][0]['lon']}")
                yield [page['title'], page['coordinates'][0]['lat'],
                       page['coordinates'][0]['lon']]
            else:
                print(f"{page['title']} --- missing cords: {titles}")
                yield [page['title'], '', '']


def get_infobox(title):
    """Get the values for each field in INFOBOX_FIELDS for the title."""

    par = {'action': 'raw', 'title': title}
    url = f"https://{WIKI_LANG}.wikipedia.org/w/index.php"
    r = requests.get(url, par, timeout=5)
    lines = r.text.split('\n')
    fields = {}
    for l in lines:
        if len(l) <= 0 or l[0] != '|' or l.count('=') != 1:
            # only produce key value pairs for table rows
            continue
        key, value = l.split('=')
        key = key.strip(' |')
        value = value.strip(' []')  # strip interwiki links
        if '|' in value:
            value = value.replace('|', ', ')
        fields[key] = value
    res = []
    for field in INFOBOX_FILEDS:
        res.append(fields.get(field, ''))
    return res


def chunks(l, n):
    """Split l into chunks of n size."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def attempt(fn, *args, **kwargs):
    """Waits and attempts again in case of OSError when fn is called."""
    retry_attempts = 0
    while retry_attempts < 5:
        try:
            res = fn(*args, **kwargs)
            retry_attempts = 5  # signal success
        except OSError:
            retry_attempts += 1
            print(f"Could not connect to network, will try again in"
                  f"{retry_attempts * 5} seconds...")
            time.sleep(retry_attempts * 5)
    return res


site = wiki.Wiki(f"https://{WIKI_LANG}.wikipedia.org/w/api.php")

c_params = {'action': 'query', 'list': 'categorymembers',
            'cmtitle': f'Kategori:{CATEGORY_TITLE}', 'cmlimit': 500}
req = api.APIRequest(site, c_params)

# empty file if it already exists
open(f'{CATEGORY_TITLE}.csv', 'w').close()

for p in req.queryGen():
    # Get categorymemebers for CATEGORY_TITLE and scrape each page
    titles = [title['title'] for title in p['query']['categorymembers']]
    with open(f'{CATEGORY_TITLE}.csv', 'a') as cordfile:
        for c in chunks(titles, 50):
            writer = csv.writer(cordfile)
            cord_gen = attempt(get_cords, '|'.join(c))

            for pair in cord_gen:
                infobox = attempt(get_infobox, pair[0])
                writer.writerow(pair + infobox)
