#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Script for adding pages to categories and simpliying names based on csvfile.

Devloped for use in cleaning up island pages on svwiki
and adding them to correct categories. Needs to be modified to
support using with other categories/use cases.


Script reads each page from csvfile,
and does some action based on the data for that page.
Currently supports adding categories and changing names.
The action is specified via commandline arguments:

--action=add-to-category, --action=rename

Other supported arguments are:

--auto     - If the script should ask for user input for each edit
--addonly  - When adding categories, if some old category should be removed or not


Current expected csvfile structure:

article title, data

Data will be different for different actions

"""

import pywikibot
import csv
import traceback
from pathlib import Path


def specify_categories(msg, site):
    cat_list = []
    done = False
    pywikibot.output("Leave empty when done.")
    while not done:
        cat_name = pywikibot.input(msg)  # "Next category to add to. Leave empty when done.\n")
        if not cat_name:
            break
        try:
            cat = pywikibot.page.Category(site, cat_name)
            if cat.exists():
                cat_list.append(cat)
            else:
                pywikibot.output(f"Invalid category: {cat_name}, enter again.")
        except OSError as e:
            pywikibot.output(f"Invalid category: {cat_name}")
    pywikibot.output(f"Adding to categories: {cat_list}")
    return cat_list


def main(*args):

    local_args = pywikibot.handle_args(args)
    arg_list = [x.split('=') for x in local_args]
    for arg in arg_list.copy():
        if len(arg) == 1:
            # Make args flags boolean
            arg.append(True)
        elif len(arg) > 2:
            # Remove wrong formatted args
            arg_list.remove(arg)
    arg_dict = {k: v for k, v in arg_list}
    action = arg_dict.get('--action', 'add-to-category')
    addonly = arg_dict.get('--addonly', False)
    sourcefile = arg_dict.get('--source', '')
    auto = arg_dict.get('--auto', False)

    site = pywikibot.Site()

    if action == 'add-to-category':
        remove_list = specify_categories("Specify category to remove articles from:\n", site)
        category_list = specify_categories("Next category to add to:\n", site)

    if not Path(sourcefile).is_file():
        pywikibot.output(f"Could not find file {sourcefile}.")
        return

    with open(sourcefile, 'r') as csvfile:
        pagereader = csv.reader(csvfile)
        for row in pagereader:
            pywikibot.output(f"----- {row[0]} -------")
            if len(row) < 2:
                pywikibot.output(f"Missing data from row, continuing...{len(row)}")
                continue
            name, data, *_ = row
            try:
                page = pywikibot.Page(site, name)
                if not page.exists():
                    pywikibot.output(f"Page {name} does not exist, skipping")
                    continue
                cats = page.categories()
                pywikibot.output(f"categories: ,  {[x for x in cats]}")

                if action == 'add-to-category':
                    new_category = [c for c in category_list if data.lower() in
                                    c.title().lower()]
                    try:
                        old_category = [c for c in remove_list if c in cats][0]
                    except IndexError:
                        pywikibot.output(f"Warning!! -- {name} does not belong to old category {remove_list}, skipping")
                        continue
                    if new_category and new_category[0] not in cats:
                        pywikibot.output(f"Add to {new_category[0]}")
                        if auto or (pywikibot.input("Confirm Y/n: ") + 'y')[0].lower() != 'n':
                            # Add to new category
                            new_text = pywikibot.textlib.replaceCategoryInPlace(page.text, old_category,
                                                                                new_category[0], add_only=addonly)
                            page.text = new_text
                            page.save('Changed category')
                            pywikibot.output(f"Adding to category {new_category}")

                if action == 'rename':
                    new_name = data
                    new_page = pywikibot.page.Page(site, new_name)
                    if page.isRedirectPage():
                        pywikibot.output(f"!!!!!  Page {name} is only a redirect - skipping")
                        continue
                    if new_page.exists():
                        pywikibot.output(f"!!!!!  Cannot move {name} to existing page {new_name}")
                        continue
                    pywikibot.output(f"Moving {name} ----> {new_name}")
                    summary = 'Förenklar sidonamn baserat på ' \
                              'https://sv.wikipedia.org/wiki/Wikipedia:Projekt_Fredrika/' \
                              'Nagu_%C3%B6ar/Namnbytesf%C3%B6rslag'
                    if auto or (pywikibot.input("Confirm Y/n: ") + 'y')[0].lower() != 'n':
                        try:
                            site.movepage(page, new_name, summary)
                        except Exception as e:
                            pywikibot.output(f"Could not move page {name}: {e}")
                    else:
                        pywikibot.output(f"Not moving page {name}")

                if action == 'list':
                    if auto or (pywikibot.input("Continue Y/n: ") + 'y')[0].lower() == 'n':
                        break

            except Exception as e:
                pywikibot.output(f"Error reading {name}:"
                                 f"{e}\n{traceback.format_exc()}")

    pywikibot.output("Finished!")


if __name__ == '__main__':
    main()
