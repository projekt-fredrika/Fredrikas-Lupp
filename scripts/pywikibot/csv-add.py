#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Script for adding pages to categories and simpliying names based on csvfile.

Devloped for use in cleaning up island pages on svwiki
and adding them to correct categories. Needs to be modified to
support suing with other categories/use cases.


Script reads each page from csvfile,
checks if it already is in correct category,
otherwise asks user for confirmation and adds page to the cateogry.
If the csvfile contains new name proposals, move the page to the new name.

Current expected csvfile structure:

Row: name, lon, lat, municipality, new name 1*, new name 2*

* - optional


WIP - DOES NOT EDIT WIKIPEDIA YET
"""

import pywikibot
import csv
import traceback


def specify_categories(category_list, site):
    done = False
    while not done:
        cat_name = pywikibot.input("Next category to add to. Leave empty when done.\n")
        if not cat_name:
            break
        try:
            cat = pywikibot.page.Category(site, cat_name)
            if cat.exists():
                category_list.append(cat)
            else:
                pywikibot.output(f"Invalid category: {cat_name}, enter again.")
        except OSError as e:
            pywikibot.output(f"Invalid category: {cat_name}")
    pywikibot.output(f"Adding to categories: {category_list}")


def main(*args):

    local_args = pywikibot.handle_args(args)
    site = pywikibot.Site()

    c_nagu = pywikibot.page.Category(site, 'Kategori:Öar i Nagu')
    category_list = []
    specify_categories(category_list, site)

    with open('svar_kommuner.csv', 'r') as csvfile:
        pagereader = csv.reader(csvfile)
        for row in pagereader:
            if len(row) < 5:
                pywikibot.output(f"Missing data from row, continuing...{len(row)}")
                continue
            name, lon, lat, county, *_ = row
            name1 = row[5] if len(row) > 5 else ''
            name2 = row[6] if len(row) > 6 else ''
            try:
                page = pywikibot.Page(site, name)
                cats = page.categories()
                pywikibot.output(f"{name}, categories: ,  {[x for x in cats]}")

                new_category = [c for c in category_list if county.lower() in
                                c.title().lower()]
                if new_category and new_category[0] not in cats:
                    pywikibot.output(f"Add to {new_category[0]}")
                    if (pywikibot.input("Confirm Y/n: ") + 'y')[0].lower() != 'n':
                        # Add to Kategori: Öar i Nagu
                        # page.text += '\n' + c_nagu.aslink()
                        # page.save('Added category')
                        pywikibot.output(f"Adding to category {new_category}")
                    if name1 or name2:
                        option = pywikibot.input(f"Move page to:\n1. {name1}\n2. "
                                                 f"{name2}\n3. Specify other "
                                                 f"name\n"
                                                 f"Other: Don't move page\n")
                        if option == '1':
                            pywikibot.output(f"Moving {name} to {name1}")
                            # Move page with pywikibot
                        elif option == '2':
                            pywikibot.output(f"Moving {name} to {name2}")
                            # Move page with pywikibot
                        elif option == '3':
                            new_name = pywikibot.input(f"Specify new name for "
                                                       f"{name}:\n")
                            pywikibot.output(f"Moving {name} to {new_name}")
                            # Move page with pywikibot
                        else:
                            pywikibot.output(f"Not moving page {name}")
            except Exception as e:
                pywikibot.output(f"Error reading {name}:"
                                 f"{e}\n{traceback.format_exc()}")
            # if (pywikibot.input("continue Y/n: ") + 'y')[0].lower() == 'n':
            #     break

    pywikibot.output("Finished!")


if __name__ == '__main__':
    main()
