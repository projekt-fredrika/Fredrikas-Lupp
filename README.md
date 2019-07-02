# Fredrikas Lupp

Fredrikas Lupp is a tool for analyzing categories or lists of pages on Wikipedia.
Fredrikas Lupp works by using the [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page).

Currently Fredrikas Lupp is developed to be used with Swedish or Finnish as primary language.
It does not yet support using other languages but is planned to have better support.

## Requirements & Installation

Fredrikas Lupp requires Python 3.6 or later. It uses [Wikitools](https://github.com/alexz-enwp/wikitools/tree/py3) python 3 branch
for communicating with Mediawiki. 

To install:

```bash
# clone this repository
git clone https://github.com/projekt_fredrika/fredrikas_lupp
cd fredrikas_lupp

# Install dependencies
pip3 install -r requirements.txt
```

## Usage

The primary usage for Fredrikas Lupp is to scrape a category on Wikipedia and compare the pages in the category between
a few languages to find where the primary language is lacking compared to others. The data that is scraped is saved as
a json file.

Fredrikas Lupp can then produce a table of the data to visualize these differences either as
html or wikitext markup.



### Basic Usage

```bash
python3 fredrikas_lupp.py scrape Nagu
```
Will run a scrape for the category Nagu, save a json file with the data, and produce a html file with a formatted report.
When used like this the default language used are Swedish (sv) as primary, Finnish (fi) as secondary and en and de as other languages.

To specify and use other languages:
```bash
python3 fredrikas_lupp.py scrape Nagu 'en|sv|no|dk'
```
However, currently using other languages is not yet fully supported.

More help and other commands can be found using:
```bash
python3 fredrikas_lupp.py help
# or
python3 fredrikas_lupp.py scrape help  # all commands can be used with help to get additinal information
```

### Lists of pages

Fredrikas Lupp also supports analyzing specific lists of pages instead of only categories. To do this, supply the scrape
command with a filename with the `.txt` filetype. Fredrikas Lupp will search for a file of that name containing a list
of pages to analyze.
```bash
# Looks for a file named Cities.txt in the same directory as the script
python3 fredrikas_lupp.py scrape Cities.txt
```
The file should contain one page on each line:
```
# Cities.txt
Helsinki
Stockholm
Oslo
Copenhagen
Tallinn
```

### Publishing

Fredrikas Lupp also supports uploading reports formatted in wikitext to a wikimedia site. To publish a category, a json
file for that category is required, which can be scraped using the `scrape` command. The report can the be published
using:
```bash
python3 fredrikas_lupp.py publish Nagu
```
Publishing can either be done interactively, inputting which url to publish to and user credentials, or autmatically
using enviroment variables. This requires the variables `WIKISITE, WIKIUSER, WIKIPASSWORD`. If one of them is not found,
Fredrikas Lupp will ask the user for them.

## File structure

The files produced by Fredrikas Lupp are saved in separate directories for different files, with subdirectories based
based on timestamps of the data.


Example file structure:
```
Fredrikas Lupp
|
+-- fredrikas_lupp.py  # Launch script
|
+-- lupp  # Modules used by launch script
|  |
|  +-- __init__.py
|  |
|  +-- fmt.py
|  |
|  +-- html.py
|  |
|  +-- plot.py
|  |
|  +-- scrape.py
|  |
|  +-- utils.py
|  |
|  \-- wikitext.py
|
+-- json  # Json files where all data from each scrape is stored
|  |
|  \-- 1970-01-01
|     |
|     \-- example.json
|
+-- html  # HTML formatted files
|  |
|  \-- 1970-01-01
|     |
|     \-- c_example.html
| 
+-- pprint  # Same as json files but pretty printed to be more human readable
|  |
|  \-- 1970-01-01
|     |
|     \-- example.txt
| 
+-- wikitext  # Wikitext markup formatted files
|  |
|  \-- 1970-01-01
|     |
|     \-- c_example.txt
| 
\-- analysis  # PDF files with plot and data table for analysis of multiple json files
   |
   \-- example_sv_plot.pdf
```
