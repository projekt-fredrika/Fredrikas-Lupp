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

import csv
import re
import traceback
from math import radians, sin, cos, asin, sqrt, atan2, degrees
from pathlib import Path

import pywikibot


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


def distance_and_direction(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = [radians(float(c)) for c in [lat1, lon1, lat2, lon2]]

    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))

    km = 6367 * c

    # compass direction calculation
    x = sin(d_lon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - (sin(lat1) * cos(lat2) * cos(d_lon))
    bearing = (degrees(atan2(x, y)) + 360) % 360
    dirs = ['norr', 'nordost', 'öster', 'sydost', 'söder', 'sydväst', 'väster', 'nordväst']
    dir_idx = int((bearing + 22.5) / 45 - 0.02)
    return km, dirs[dir_idx % 8]


def edit_page(action, site, name, data, category_list=(), remove_list=(), addonly=False, auto=False):
    if category_list is None:
        category_list = []
    page = pywikibot.Page(site, name)
    if not page.exists():
        pywikibot.output(f"Page {name} does not exist, skipping")
        return

    if action == 'add-to-category':
        cats = page.categories()
        pywikibot.output(f"categories: ,  {[x for x in cats]}")
        new_category = [c for c in category_list if data.lower() in
                        c.title().lower()]
        try:
            old_category = [c for c in remove_list if c in cats][0]
        except IndexError:
            pywikibot.output(f"Warning!! -- {name} does not belong to old category {remove_list}, skipping")
            return
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
            return
        if new_page.exists():
            pywikibot.output(f"!!!!!  Cannot move {name} to existing page {new_name}")
            return
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
            return

    if action == 'text-rename':
        changes_made = 0

        # Calculate coords and names from data
        lat, lon, close, boat = data.split('|')
        try:
            close_cords = pywikibot.page.Page(site, close).coordinates()[0]
        except IndexError:
            try:
                close_cords = pywikibot.page.Page(site, close.split(', ')[0]).coordinates()[0]
            except IndexError:
                pywikibot.output("Cannot find close coords!!!!!")
                return
        if " (" in close:
            closelink = f"[[{close}|{close.split(' (')[0]}]]"
            close = close.split(' (')[0]
        elif ", " in close:
            closelink = f"[[{close}|{close.split(', ')[0]}]]"
            close = close.split(', ')[0]
        else:
            closelink = f"[[{close}]]"
        if " (" in boat:
            boatlink = f"[[{boat}|{boat.split(' (')[0]}]]"
            boat = boat.split(' (')[0]
        elif ", " in boat:
            boatlink = f"[[{boat}|{boat.split(', ')[0]}]]"
            boat = boat.split(', ')[0]
        else:
            boatlink = f"[[{boat}]]"

        boatnames = {
            "M/S Eivor": ['Pärnäs', 'Nagu Berghamn', 'Nötö', 'Aspö', 'Jurmo', 'Utö'],
            "M/S Nordep": ['Kirjais', 'Brännskär', 'Stenskär', 'Gullkrona', 'Pensar',
                           'Grötö', 'Kopparholm', 'Träskholm', 'Björkö', 'Trunsö',
                           'Sandholm', 'Lökholm', 'Borstö', 'Knivskär', 'Bodö', 'Långholm och Träskholm'],
            "M/S Falkö": ['Kyrkbacken, Nagu', 'Kyrkbacken', 'Själö', 'Innamo', 'Järvsor', 'Maskinnamo', 'Åvensor'],
            "M/S Östern": ['Kyrkbacken, Nagu', 'Kyrkbacken', 'Själö'],
            "M/S Cheri": ['Pärnäs', 'Krok', 'Mattnäs', 'Fagerholm', 'Ängsö', 'Tveskiftsholm',
                          'Nagu Berghamn', 'Hummelholm', 'Östra Rockelholm', 'Ytterstholm', 'Brännskär', 'Grötö',
                          'Stenskär', 'Gullkrona', 'Kirjais']
        }

        old_text = page.text

        # Insert closest big island and Nagu in text
        start = re.compile(r'(?i)((?<=\[\[ö \(landområde\)\|ö\]\])|'
                           r'(?<=\[\[öar\]\])|(?<=\[\[klippa \(geologi\)\|klippa\]\])|'
                           r'(?<=\[\[klippor\]\])|'
                           r'(?<=\[\[skär \(landområde\)\|skär\]\])|'
                           r'(?<=\[\[ö \(landområde\)\|del av en ö\]\])) i')
        if re.search(start, page.text) and not re.search(r'(?<!samhälle är )\[\[Nagu\]\]', page.text):
            replacement = f" nära {closelink} i [[Nagu]], "
            if page.title().split(', ')[0] == close:
                replacement = f" i [[Nagu]], "
            pywikibot.output(f"{re.search(start, page.text).group()} --> {replacement})")
            page.text, n = re.subn(start, replacement, page.text)
            changes_made += n

        # Simplify "i kommunen Pargas"
        pargas_stad = re.compile(r'(och )?i kommunen \[\[(Pargas stad\|)?Pargas\]\]')
        if re.search(pargas_stad, page.text):
            replacement = f"i [[Pargas stad]]"
            pywikibot.output(f"{re.search(pargas_stad, page.text).group()} --> {replacement}")
            page.text, n = re.subn(pargas_stad, replacement, page.text)
            changes_made += n

        # Change Pargas to Pargas stad
        pargas_muni = re.compile(r'(?<=\| municipality)\s*= \[\[(Pargas stad\|)?Pargas\]\]')
        if re.search(pargas_muni, page.text):
            replacement = f"{' ' * 12}= [[Pargas stad]]"
            pywikibot.output(f"{re.search(pargas_muni, page.text).group()} --> {replacement}")
            page.text, n = re.subn(pargas_muni, replacement, page.text)
            changes_made += n

        # Insert Nagu Kommundel in infobox as parish field
        parish = re.compile(r'(?m)(?<=municipality_type {7}= \[\[Finlands kommuner\|Kommun\]\])|'
                            r'(?<=municipality_type {7}= $)|'
                            r'(?<=municipality_type {7}=$)')
        if re.search(parish, page.text) and not re.search('parish', page.text):
            replacement = (f"\n| parish{' ' * 18}= [[Nagu]]"
                           f"\n| parish_type{' ' * 13}= Kommundel")
            pywikibot.output(f"{re.search(parish, page.text).group()} --> {replacement}")
            page.text, n = re.subn(parish, replacement, page.text)
            changes_made += n
            # Clear old district/district_type fields
            page.text, n = re.subn(r'(?<=\| district {16}=) \[\[Nagu\]\]', '', page.text)
            changes_made += n
            page.text, n = re.subn(r'(?<=\| district_type {11}=) \[\[Kommundel\]\]', '', page.text)
            changes_made += n

        elif re.search(r'(?<== \[\[Pargas stad\|Pargas\]\])|'
                       r'(?<== \[\[Pargas stad\]\])', page.text) and not re.search('parish', page.text):
            pattern = re.compile(r'(?<== \[\[Pargas stad\|Pargas\]\])|'
                                 r'(?<== \[\[Pargas stad\]\])')
            replacement = (f"\n| parish{' ' * 18}= [[Nagu]]"
                           f"\n| parish_type{' ' * 13}= Kommundel")
            pywikibot.output(f"{re.search(pattern, page.text).group()} --> {replacement}")
            page.text, n = re.subn(pattern, replacement, page.text)
            changes_made += n
            # Clear old district/district_type fields
            page.text, n = re.subn(r'(?<=\| district {16}=) \[\[Nagu\]\]', '', page.text)
            changes_made += n
            page.text, n = re.subn(r'(?<=\| district_type {11}=) \[\[Kommundel\]\]', '', page.text)
            changes_made += n

        # Insert distances to closest 1.big island, 2. Nagu kyrkbacken, 3. If missing: Åbo
        distance = re.compile(r'((?<=Ön ligger)|(?<=Öarna ligger)) omkring ')
        no_abo = re.compile(r', i den (södra|sydvästra) delen av landet, ')
        if re.search(distance, page.text) and not re.search(r'om \[\[Nagu kyrka\]\]', page.text):
            close_dist, close_dir = distance_and_direction(close_cords.lat, close_cords.lon, lat, lon)
            kyrk_dist, kyrk_dir = distance_and_direction(60.194, 21.906, lat, lon)
            close_str = 'just' if close_dist < 1 else f"omkring {close_dist:.0f} kilometer"
            replacement = (f" {close_str} {close_dir} om {closelink}, "
                           f"{kyrk_dist:.0f} kilometer {kyrk_dir} om [[Nagu kyrka]], ")
            if page.title().split(', ')[0] == close:
                replacement = f" {kyrk_dist:.0f} kilometer {kyrk_dir} om [[Nagu kyrka]], "
            pywikibot.output(f"{re.search(distance, page.text).group()} --> {replacement}")
            page.text, n = re.subn(distance, replacement, page.text)
            changes_made += n
        elif re.search(no_abo, page.text) and not re.search(r'om \[\[Nagu kyrka\]\]', page.text):
            close_dist, close_dir = distance_and_direction(close_cords.lat, close_cords.lon, lat, lon)
            kyrk_dist, kyrk_dir = distance_and_direction(60.194, 21.906, lat, lon)
            abo_dist, abo_dir = distance_and_direction(60.4528, 22.2722, lat, lon)
            close_str = 'just' if close_dist < 1 else f"omkring {close_dist:.0f} kilometer"
            replacement = (f". Ön ligger {close_str} {close_dir} om {closelink}, "
                           f"omkring {kyrk_dist:.0f} kilometer {kyrk_dir} om [[Nagu kyrka]], "
                           f" {abo_dist:.0f} kilometer {abo_dir} om Åbo och ")
            if page.title().split(', ')[0] == close:
                replacement = (f". Ön ligger omkring {kyrk_dist:.0f} kilometer {kyrk_dir} om [[Nagu kyrka]], "
                               f" {abo_dist:.0f} kilometer {abo_dir} om Åbo och ")
            pywikibot.output(f"{re.search(no_abo, page.text).group()} --> {replacement}")
            page.text, n = re.subn(no_abo, replacement, page.text)
            changes_made += n

        # Insert closest ferry location and what boats traffic it at the end of intro text.
        add = re.compile(r'om (huvudstaden )?\[\[Helsingfors\]\]\.'
                         r'( Närmaste allmänna förbindelse är förbindelsebryggan vid .*\[\[M\/S.{4,8}\]\]\.)?')
        if re.search(add, page.text):  # and not re.search(r'förbindelse|trafikerar', page.text):
            boats = [f"[[{k}]]" for k, v in boatnames.items() if boat in v]
            boats_plural = 'en' if len(boats) == 1 else 'arna'
            boats_str = ' och '.join(boats)
            replacement = 'om [[Helsingfors]].'
            if boat == name.split(', ')[0]:
                replacement = replacement + f" Förbindelsebåt{boats_plural} {boats_str} trafikerar {name}."
            else:
                replacement = replacement + (f" Närmaste allmänna förbindelse är förbindelsebryggan"
                                             f" vid {boatlink} som trafikeras av {boats_str}.")
            pywikibot.output(f"{re.search(add, page.text).group()} -->{replacement}")
            page.text, n = re.subn(add, replacement, page.text)
            changes_made += n
        # Push changes to wikipedia
        if changes_made == 0 or old_text == page.text:
            return
        elif ((auto and changes_made == 6) or (auto and changes_made == 3) or
              (pywikibot.input(f"Continue with {changes_made} changes Y/n: ") + 'y')[0].lower() != 'n'):
            page.save("Lägger till kommundel, avstånd och förbindelser")
        else:
            pywikibot.output(f"No changes made")

        # Chagnes links to redirect pages to direct to main page instead.
        pat = re.compile(f'^.*{re.escape(name)}.*$')
        for p in page.backlinks():
            hit = re.search(pat, p.text)
            if hit:
                if "OMDIRIGERING" in hit.group():
                    for rp in p.backlinks():
                        hit = re.search(re.escape(p.title()), rp.text)
                        if hit and rp.namespace() == 0:
                            pywikibot.output(f"<<< {rp.title()} >>>\n{hit.group()}  -->  {name}")
                            rp.text, n = re.subn(re.escape(p.title()), name, rp.text)
                            changes_made += n
                            # Push changes to wikipedia
                            rp.save("Ändrar länk att peka på rätt sida, inte redirect")
        pywikibot.output(f"Made {changes_made} changes to {name}")


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

    remove_list = []
    category_list = []
    if action == 'add-to-category':
        remove_list = specify_categories("Specify category to remove articles from:\n", site)
        category_list = specify_categories("Next category to add to:\n", site)

    if not Path(sourcefile).is_file():
        pywikibot.output(f"Could not find file {sourcefile}.")
        return

    with open(sourcefile, 'r') as csvfile:
        pagereader = csv.reader(csvfile)
        for row in pagereader:
            pywikibot.output(f"\n\n----- {row[0]} -------")
            if len(row) < 2:
                pywikibot.output(f"Missing data from row, continuing...{len(row)}")
                continue
            name, data, *_ = row
            try:
                edit_page(action, site, name, data,
                          category_list=category_list,
                          remove_list=remove_list,
                          addonly=addonly,
                          auto=auto)
            except Exception as e:
                pywikibot.output(f"Error reading {name}:"
                                 f"{e}\n{traceback.format_exc()}")

    pywikibot.output("Finished!")


if __name__ == '__main__':
    main()
