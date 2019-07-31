"""
Different utility functions for the lupp.scrape module
"""

import json
import os
import sys
import time
from datetime import datetime, date
from pathlib import Path
from pprint import pprint


def now_ymd_hms():
    """Format date to Year Month Day Hour Minute Second"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_dmy_hm():
    """Format date to Year Month Day Hour Minute"""
    return datetime.now().strftime("%d.%m.%Y kl. %H:%M")


def now_ymd():
    """Format date to Year Month Day"""
    return date.today().strftime("%Y-%m-%d")


def days_between(d1, d2):
    """Calculate amount of days between two dates"""
    d1 = datetime.strptime(d1, "%Y-%m-%d")
    d2 = datetime.strptime(d2, "%Y-%m-%d")
    return abs((d2 - d1).days)


def loading_bar(loading, data=None):
    """Prints loading bar that keeps repeating until loading['status'] is set to True

    Function that displays a loading bar that keeps repeating until
    :parameter loading['status'] is set to True
    :parameter data, dict containing 'pages', from where number of pages read are displayed

    Intended to run in own thread while other threads work until all work is done
    Will never terminate if run in main thread!"""
    if data is None:
        data = {}
    i = 0
    page_cnt = 0
    shown_categories = set()
    while True:
        if data and 'pages'in data:
            page_cnt = len(data['pages'])
        if data and 'categories' in data:
            new_cats = set(data['categories'].keys())
            for new in new_cats.difference(shown_categories):
                print(f"\rCategory title: {new}")
            shown_categories = new_cats
        print(f"\rScraping pages [{'-'*(i // 500) + '>':<20}] {page_cnt} pages read", end='')
        if not loading['status']:
            print(f"\rScraping Done! {page_cnt} pages read")
            break
        i = (i + 1) % 10000
        time.sleep(0.001)


def make_dir(outdir_path):
    """Create new direcotory, unless it already exists"""
    for path in list(reversed(outdir_path.parents)) + outdir_path:
        if not path.exists():
            path.mkdir()


def save_utf_file(utf_file, fmt, s, dir_date=""):
    """Saves the data from s to a file

    Saves the content of utf_file to a file in a folder based on format and date.
    All formats are saved in different folders with subfolders for different dates.
    :param utf_file: Name of category/list of the data
    :param fmt: What format the data is in, also specifies where file is saved
    :param s: The data to be saved
    :param dir_date: Specifies subfolder where file is to be saved. If empty, current date is used
    """
    path = Path('.') / fmt / dir_date
    make_dir(path)
    utf_file = path / utf_file
    with open(utf_file, "w", encoding='utf-8') as f:
        f.write(s)
        print(f"Skapade {fmt}-filen {utf_file} ({len(s)} tecken)")


def save_json_file(json_file, j, dir_date=""):
    """Save python dict as json file

    Save datta from python dict as a json file. Two files are created, one normal json file and
    pretty printed text file with more easily readable json.
    The files are created in json/ and pprint/ folders inside subfolders based the privided date

    :param json_file: Name for the files
    :param j: Python dict with the data
    :param dir_date: Date for subfolder. If empty, current date is used
    """
    json_dir = Path("json") / dir_date
    make_dir(json_dir)
    pprint_dir = Path("pprint") / dir_date
    make_dir(pprint_dir)
    if "json" not in json_file.parts:
        json_file = Path("json") / dir_date / json_file
        ppfile = Path("pprint").joinpath(*json_file.parts[1:])
    else:
        json_file = Path("json") / dir_date / json_file.name
        ppfile = Path("pprint").joinpath(*json_file.parts[1:])
    json.dump(j, open(json_file, 'w'))
    print(f"\nSkrev json -filen {json_file} ({len(str(j))} tecken)")
    ppfile = ppfile.with_suffix('.txt')
    with open(ppfile, "w", encoding='utf-8') as fout:
        pprint(j, fout)
    print(f"\nSkrev pprint-filen {ppfile}")


def save_used_cache(filename):
    """Saves which cache file was last used"""
    cache_title = filename.stem
    used_cache = {'cache': filename.as_posix(), 'title': cache_title}
    json.dump(used_cache, open(Path("json") / "used_cache.json", 'w'))
    print(f"Used cache: {filename}")


def save_as_csv(scalars, has_title, other, tricky, category):
    """Create csv file of the perameters, unused"""

    # Header for CSV file
    csv = "Title;URL;Category;"
    csv += ";".join(tricky + scalars + has_title + other) + "\n"
    save_utf_file(f"c_{category}.csv", "csv", csv)


def find_path(category):
    """Try to resolve path for json cache file for {category}"""
    json_path = Path('json')
    json_path = list(json_path.glob(f'*/{category.replace(" ", "_")}.json'))
    json_path.sort(reverse=True)
    if json_path:
        json_path = json_path[0]
    else:
        path_with_date = Path("json") / str(date.today())
        make_dir(path_with_date)
        json_path = path_with_date / f"{category.replace(' ', '_')}.json"
    return json_path


def exit_program(start):
    """Exit program and print stats for running time"""
    end = datetime.now()
    print(f"\nfredrikas_lupp.py slutade {end.strftime('%H:%M')} total svarstid {(end - start).seconds} s")
    sys.exit()


def list_json():
    """Print list of all json-files in json/ directory"""
    files = {}
    for dirpath, dirnames, filenames in os.walk("json"):
        for filename in (f for f in filenames if f.endswith(".json")):
            if "err_" in filename:
                continue
            if filename[:-5] in files.keys():
                files[filename[:-5]].append(dirpath[7:])
                files[filename[:-5]].sort(reverse=True)
                continue
            files.update({filename[:-5]: [dirpath[7:]]})
    del files["used_cache"]
    files_l = sorted(files, key=lambda x: files[x])
    for f in files_l:
        buffer = 50 - len(f)
        print(f"{f} {'-' * buffer} {files[f]}")
