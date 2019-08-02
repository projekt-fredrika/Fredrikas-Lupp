#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script for getting detailed stats for a user on wikipedia.

Takes commandline arguments to specify user, timerange and
which language sites to check.

--user=     - Specify user to check


--langs=    - Which languages of wikipedia to check. Pipe ('|') separated list
              Default is --langs=sv|fi|en|de|fr|ru|ee

--interval=  - Time interval to check edits from. Is specified in format.
              1970-01-01--2050-01-01
              Default is --interval=1970-01-01--2050-01-01
              Start and end can also be specified separately with --start, --end

--start=     - See --interval


--end=       - See --interval


Does not yet support wikidata or other site that are not simply language variants of wikipedia.
"""
import sys

import pprint
import csv
from datetime import datetime
from wikitools import wiki, api
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_args():
    """Parse commandline arguments in format --PARAM=VALUE."""
    args = {}
    for arg in sys.argv:
        if '--user' in arg and '=' in arg:
            args['user'] = arg.split('=')[1]
        if '--start' in arg and '=' in arg:
            args['from_date'] = datetime.strptime(arg.split('=')[1], "%Y-%m-%d")
        if '--end' in arg and '=' in arg:
            args['to_date'] = datetime.strptime(arg.split('=')[1], "%Y-%m-%d")
        if '--interval' in arg and '=' in arg:
            interval = arg.split('=')[1]
            start = interval[:len(interval) // 2].strip('-')
            end = interval[len(interval) // 2:].strip('-')
            args['from_date'] = datetime.strptime(start, "%Y-%m-%d")
            args['to_date'] = datetime.strptime(end, "%Y-%m-%d")
        if '--langs' in arg and '=' in arg:
            args['langs'] = arg.split('=')[1].split('|')
    return args


def get_sites(langs):
    """Take list of languages and return wikitools instances of the sites."""
    return {l: wiki.Wiki(f"https://{l}.wikipedia.org/w/api.php") for l in langs}


def get_usercontribs(lang, site, params, stop_date):
    user_contrib = []
    req = api.APIRequest(site, params)
    for resp in req.queryGen():
        pages = resp['query']['usercontribs']
        before_end = [p for p in pages if datetime.strptime(p['timestamp'], "%Y-%m-%dT%H:%M:%SZ") > stop_date]
        user_contrib.extend(before_end)
        if len(pages) != len(before_end):
            # Has hit stop date if some pages are filtered away
            break
    return lang, user_contrib


def analyze_stats(data):
    """Take data dict with all edits and return dict with stats such as count/additions/deletions per lang."""
    stats = {}
    data = {k: v for k, v in data.items() if v}
    stats['langs'] = list(data.keys())
    stats['user'] = data[stats['langs'][0]][0]['user']
    all_items = [item for sublist in data.values() for item in sublist]
    stats['count'] = len(all_items)
    stats['additions'] = sum((int(p['sizediff']) for p in all_items if int(p['sizediff']) > 0))
    stats['deletions'] = sum((int(p['sizediff']) for p in all_items if int(p['sizediff']) < 0))
    articles = [item for item in all_items if int(item['ns']) == 0]
    stats['article_count'] = len(articles)
    stats['article_additions'] = sum((int(p['sizediff']) for p in articles if int(p['sizediff']) > 0))
    stats['article_deletions'] = sum((int(p['sizediff']) for p in articles if int(p['sizediff']) < 0))
    for l in stats['langs']:
        lang_pages = data[l]
        stats[f"{l}_count"] = len(lang_pages)
        stats[f"{l}_additions"] = sum((int(p['sizediff']) for p in lang_pages if int(p['sizediff']) > 0))
        stats[f"{l}_deletions"] = sum((int(p['sizediff']) for p in lang_pages if int(p['sizediff']) < 0))
        lang_articles = [item for item in lang_pages if int(item['ns']) == 0]
        stats[f"{l}_article_count"] = len(lang_articles)
        stats[f"{l}_article_additions"] = sum((int(p['sizediff']) for p in lang_articles if int(p['sizediff']) > 0))
        stats[f"{l}_article_deletions"] = sum((int(p['sizediff']) for p in lang_articles if int(p['sizediff']) < 0))
    return stats


def main():
    """Main function, parses commandline arguments, queries wikipedia API and saves data in txt and csv files."""
    args = get_args()
    user = args.get('user', '')
    from_date = args.get('from_date', datetime(1970, 1, 1))
    to_date = args.get('to_date', datetime(2050, 1, 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"ARGS: {args}, from_date: {from_date} to_date: {to_date}")
    user_contrib = {}
    params = {'action': 'query', 'list': 'usercontribs',
              'ucuser': user, 'uclimit': 500,
              'ucprop': 'title|sizediff|timestamp', 'ucstart': to_date}
    sites = get_sites(args.get('langs', ['sv', 'fi', 'en', 'de', 'fr', 'ru', 'ee']))
    with ThreadPoolExecutor(max_workers=5) as tpe:
        futures = (tpe.submit(get_usercontribs, l, s, params, from_date) for l, s in sites.items())
        for fut in as_completed(futures):
            try:
                lang, res = fut.result()
                user_contrib[lang] = res
            except Exception as e:
                print(f"Exception retrieving data: {e}")
    stats = analyze_stats(user_contrib)
    interval = from_date.strftime('%Y-%m-%d') + '--' + to_date[:10]
    with open(f"{user}_{interval}.txt", 'w') as userfile:
        for key, value in stats.items():
            userfile.write(f"{key}: {value}\n")
    with open(f"{user}_{interval}.csv", 'w') as csvfile:
        writer = csv.writer(csvfile)
        for lang, pages in user_contrib.items():
            for page in pages:
                fields = [lang, page['title'], page['timestamp'], page['sizediff'], page['ns']]
                writer.writerow(fields)
    pprint.pprint(user_contrib)
    pprint.pprint(stats)


if __name__ == '__main__':
    main()
