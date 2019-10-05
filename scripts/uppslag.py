#! /usr/bin/env python3
# coding: utf-8
"""For creating uppslagsverket Nagu"""

import csv
from lxml import etree
from pathlib import Path
import requests
from urllib.parse import unquote

from island_desc import island_desc, get_island_dict


def get_pages(file):
    """Iterates over rows in csv file."""
    with open(file) as f:
        next(f)     # ignore headers in csv file
        r = csv.reader(f)
        yield from r


def get_page(url):
    """Gets HTML for a specific page."""
    try:
        r = requests.get(url)
        return r.text
    except requests.exceptions.MissingSchema as _:
        print(f"Incorrect url missing schema, skipping {url}")
        return ""


def clean(name, text):
    page = etree.HTML(text)
    top_tag = page.xpath('//div[@class="mw-parser-output"]')[0]

    # Remove loads of unnecessary html elements
    for el in page.xpath('//meta | //script | //style | //noscript |'
                         ' //span[@class="mw-editsection"] |'
                         ' //table[contains(@class,"infobox")] |'
                         ' //table[contains(@class,"navbox")] |'
                         ' //div[contains(@class,"metadata")] |'
                         ' //div[@id="toc"] |'
                         ' //div[contains(@class,"noprint")] |'
                         ' //table[contains(@style,"background-color: #f9f9f9")] |'
                         ' //comment() |'
                         ' //table[contains(@class,"ambox")]'):
        # print(el)
        el.getparent().remove(el)

    # convert references to simple <referens>1</referens>
    for ref in page.xpath('//sup[@class="reference"]'):
        refnr = ""
        for e in ref.iter(tag='span'):
            if e.tail:
                refnr += refnr + e.tail
        [ref.remove(el) for el in ref]
        ref.text = refnr
        ref.tag = 'referens'
        ref.attrib.clear()

    # convert h1, h2 ... to rubrik1, rubrik2 ...
    for n in range(1, 6):
        for rub in page.xpath(f'//h{n}'):
            if len(rub):
                title = rub[-1].attrib.get('id', '???????').replace('_', ' ')
                rub.text = title
            [rub.remove(el) for el in rub]
            rub.tag = f'rubrik{n}'

    # Renaming simple elements
    for el in top_tag.xpath('./p'):
        el.tag = 'stycke'

    # Renaming simple elements
    for el in top_tag.xpath('.//ul'):
        el.tag = 'lista'

    # Renaming simple elements
    for el in top_tag.xpath('.//li'):
        el.tag = 'listpunkt'

    # ?????? remove some unnecessary elements TODO move to general removeal loop
    for el in page[1][1:]:
        # print(el.attrib)
        page[1].remove(el)

#   toc = page.xpath('//div[@id="toc"]')[0]
#   toctext = []
#   for el in toc.iter():
#       if el.text:
#           toctext.append(get_text(el))
#   [toc.remove(el) for el in toc]
#   for i, a in enumerate(toctext):
#       try:
#           print(a)
#           nr = float(a)
#           section = etree.Element('rubrik')
#           section.text = f"{a}. {toctext[i + 1]}"
#           toc.append(section)
#       except ValueError:
#           print("Not floating")
#   print("TOC --- ", toc, len(toc))
#   for el in page.xpath('//div[@class="thumbcaption"]'):
#       el.tag = 'bildtext'
#       el.attrib.clear()
#       link_to_text(el[0])

    # Convert images to <bild> + <bildtext>
    image_urls = set()
    for el in top_tag.xpath('.//img'):
        parent = el.getparent()

        if parent is None or parent.getparent() is None:
            print("Problem reading parernt of image tag")

        # do while loop
        while parent.getparent() is not None and parent.getparent() is not top_tag:
            parent = parent.getparent()
        if parent.getparent() is None:
            top_tag.insert(-2, parent)
        idx = top_tag.index(parent)
        parent.tag = 'bild'
        for img_desc in parent.xpath('.//div[@class="thumbcaption"]'):
            img_desc.tag = 'bildtext'
            img_desc.attrib.clear()
            link_to_text(img_desc[0])
            # Add img_desc after <bild> as child of top element
            top_tag.insert(idx + 1, img_desc)
        parent.attrib.clear()
        image_urls.add(el.attrib['src'])
        # print(f"Added url: {el.attrib['src']}")
        # add_image_to_list(el.attrib['src'])
        parent.attrib['href'] = unquote(f"file://bilder/{el.attrib['src'].split('/')[-1]}")
        el.getparent().remove(el)
        for child in parent:
            parent.remove(child)

    #  file with list of all images

    # convert all other <a> tags to normal text
    for el in page.xpath('//a'):
        link_to_text(el)

    # Clean up reference list
    for el in top_tag.xpath('.//ol[@class="references"]'):
        for ref_el in el:
            nr = ref_el.attrib['id'][-1]
            ref_el.attrib.clear()
            link_to_text(ref_el[0])
            ref_el.text = f"{nr}.{ref_el.text}"
        el.tag = 'referenslista'
        el.attrib.clear()

    # Add to level title and change top level tag to 'artikel'
    top_tag.tag = 'artikel'
    top_tag.attrib.clear()
    top_tag.attrib['titel'] = name
    title_tag = etree.Element('rubrik1')
    title_tag.text = name
    top_tag.insert(0, title_tag)
    # print(f"LENGTH: {len(image_urls)}")
    return top_tag, image_urls


def add_image_to_list(imgs):
    with open(Path('..') / 'bilder.txt', 'w') as f:
        for img in imgs:
            f.write(f"https:{img}\n")


def get_text(el) -> str:
    el_text = el.text if el.text else ""
    el_tail = el.tail if el.tail else ""
    if len(el) and el[0].tag in 'bai':
        return el_text + get_text(el[0]) + el_tail
    else:
        return el_text + el_tail


def link_to_text(el):
    parent = el.getparent()
    if parent is None:
        return
    if len(el):
        for child in el:
            link_to_text(child)
    par_text = parent.text if parent.text else ""
    if el.text:
        if el.getprevious() is not None:
            prev = el.getprevious()
            newtail = prev.tail + el.text if prev.tail else el.text
            el.getprevious().tail = newtail
        else:
            par_text += el.text
    if el.tail:
        if el.getprevious() is not None:
            prev = el.getprevious()
            newtail = prev.tail + el.tail if prev.tail else el.tail
            el.getprevious().tail = newtail
        else:
            par_text += el.tail
    parent.text = par_text
    parent.remove(el)
    # el.tag = 'länk'
    # if 'href' in el.attrib:
    # del el.attrib['href']


def main():
    img_urls = set()
    top_tag = etree.Element('samling')
    island_dict = get_island_dict()
    for name, url, short in get_pages(Path('../nagu-artiklar.csv')):
        print(name)
        if short:
            #article_tag = etree.Element('artikel', attrib={'titel': name})
            article_tag = etree.XML(island_desc(unquote(url[30:])))
            top_tag.append(article_tag)
        else:
            text = get_page(url)
            if not text:
                continue     # Skip when error getting page
            article_tag, article_imgs = clean(name, text)
            top_tag.append(article_tag)
            img_urls.update((unquote(x) for x in article_imgs))
    add_image_to_list(img_urls)
    string = etree.tostring(top_tag, encoding=str, pretty_print=True)
    with open(Path('..') / 'Nagu.xml', 'w') as r:
        r.write(string)


if __name__ == '__main__':
    main()
