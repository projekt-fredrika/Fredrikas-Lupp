import requests
import requests_cache
import hashlib
from urllib.parse import quote
import pandas as pd
import json
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import pandas as pd
from datetime import datetime, timedelta

requests_cache.install_cache('http_cache', expire_after=86400)

def read_list_of_categories(filepath):
    categories = []
    with open(filepath, "r") as file:
        for line in file:
            if line.startswith("#") or line.strip() == "":
                continue
            else:
                print(line.strip())
                categories.append(line.strip())
    return categories

def get_files_in_category(category):
    BASE_URL = "https://commons.wikimedia.org/w/api.php"
    params = {
        'action': 'query',
        'list': 'categorymembers',
        'cmtitle': 'Category:' + category,
        'cmlimit': 'max',
        'cmtype': 'file',
        'format': 'json'
    }
    files = []
    while True:
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        files.extend([page['title'] for page in data['query']['categorymembers']])
        if 'continue' in data:
            params.update(data['continue'])
        else:
            break
    return files

def get_image_usage(file_title):
    BASE_URL = "https://commons.wikimedia.org/w/api.php"
    params = {
        'action': 'query',
        'titles': file_title,
        'prop': 'globalusage',
        'gulimit': 'max',
        'format': 'json'
    }
    response = requests.get(BASE_URL, params=params)
    data = response.json()
    page_id = list(data['query']['pages'].keys())[0]
    return [(entry['wiki'], entry['title']) for entry in data['query']['pages'][page_id]['globalusage']]

def construct_image_url(filename):
    # Remove 'File:' prefix and spaces for MD5 hash calculation
    name_without_prefix = filename.replace("File:", "").replace(" ", "_")
    md5_hash = hashlib.md5(name_without_prefix.encode('utf-8')).hexdigest()
    url_path = f"/wikipedia/commons/{md5_hash[0]}/{md5_hash[0:2]}/{quote(name_without_prefix)}"
    url_path = url_path.replace("/","%2F")
    return url_path

def get_image_views(file_path, start = "2022110600", end = "2023110500"):
    # uses https://wikitech.wikimedia.org/wiki/Analytics/AQS/Mediarequests
    referer = "all-referers" # all-referers, internal, external, unknown, or the specific wiki where the media was loaded
    agent = "user" # all-agents, spider, user
    granularity = "monthly" # monthly or daily
    file_path = construct_image_url(file_path)
    
    url = f"https://wikimedia.org/api/rest_v1/metrics/mediarequests/per-file/{referer}/{agent}/{file_path}/{granularity}/{start}/{end}"
    response = requests.get(url)
    data = ""
    sum = 0
    if response.status_code == 200:
        data = response.json()
        for item in data['items']:
            sum = sum + int(item['requests'])
        return sum
    else:
        print(f"Failed to retrieve image views with url: {response.url} ")
        print(f"Status code: {response.status_code}")
        return None

def get_history_and_find_image_addition(page_title, file_title, wiki, rvstart='2000-01-01T00:00:00Z'):
    file_name = file_title.split(":", 1)[-1]
    item_id = None
    last_continue = ""
    if wiki == "www.wikidata.org":
        return find_file_revision_on_wikidata(page_title, file_name)
    if wiki.endswith("wikipedia.org"):
        item_id = get_wikidata_qid(page_title, wiki.split(".")[0])
    BASE_URL = f"https://{wiki}/w/api.php"
    i = 0
    while True:
        params = {
            'action': 'query',
            'prop': 'revisions',
            'titles': page_title,
            'rvprop': 'ids|user|timestamp|content',
            'rvlimit': 'max',  # Fetch as many revisions as possible
            'rvdir': 'newer',  # Start from the order revisions and go to newer
            'rvslots': 'main',
            'rvstart': rvstart, # could be filtered to only revisions after 1st April 2022 (when project was started)
            'format': 'json',
        }
        i = i+1
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        page_id = next(iter(data['query']['pages']), None)

        # If the page does not exist or other error occurs
        if page_id is None:
            break
        if 'revisions' not in data['query']['pages'][page_id]:
            break
        revisions = data['query']['pages'][page_id]['revisions']
        for rev in revisions:  # Reverse to start from newest
            #print(rev['slots']['main'])
            current_content = rev['slots']['main'].get('*',"error")
            if current_content == "error": 
                print(f"WARNING ERROR, no * in {page_title}")
            if file_name in current_content or file_name.replace(" ","_") in current_content:
                return rev['user'], rev['timestamp'], item_id, i

        # If there's more data, continue
        if 'continue' in data:
            if last_continue is not data['continue']:
                break
            else:
                params.update(data['continue'])
        else:
            break

    return None, None, item_id, i  # Image addition not found

def find_file_revision_on_wikidata(item_id, file_name, rvstart='2010-01-01T00:00:00Z'):
    BASE_URL = "https://www.wikidata.org/w/api.php"

    i = 0
    last_continue = ""
    while True:
        params = {
            'action': 'query',
            'prop': 'revisions',
            'titles': item_id,  # e.g., 'Q12345'
            'rvlimit': 'max',
            'rvprop': 'ids|user|timestamp|content',
            'rvdir': 'newer',  
            'rvslots': 'main',
            'rvstart': rvstart,
            'format': 'json',
            'formatversion': 2
        }
        i = i+1
        response = requests.get(BASE_URL, params=params)
        data = response.json()

        # Check for valid page (there might be cases where the item doesn't exist)
        if '-1' in data['query']['pages']:
            break
        print("page in data")
        # Check each revision if file name is mentioned
        for page in data['query']['pages']:
            
            if "revisions" not in page:
                print("no revision")
                if rvstart != '2010-01-01T00:00:00Z':
                    return find_file_revision_on_wikidata(item_id, file_name, rvstart='2010-01-01T00:00:00Z')
                else:
                    break
            for revision in page['revisions']:
                content = revision['slots']['main']['content']
                content = bytes(content, "utf-8").decode("unicode_escape")
                if file_name in content or file_name.replace(" ","_") in content:
                    return revision['user'], revision['timestamp'], item_id, i
        # If there's more data, continue
        if 'continue' in data:
            if last_continue is not data['continue']:
                break
            else:
                params.update(data['continue'])
        else:
            break
    return None, None, item_id, i

def get_wikidata_qid(title, lang):
    url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "pageprops",
        "ppprop": "wikibase_item"
    }
    response = requests.get(url, params=params)
    data = response.json()
    pages = data.get("query", {}).get("pages", {})
    for _, page in pages.items():
        qid = page.get("pageprops", {}).get("wikibase_item")
        if qid:
            return qid
    return None

import requests

def get_upload_date(file_title):
    file_title = file_title.replace(' ', '_')
    file_title = file_title.split(':')[1]
    API_ENDPOINT = 'https://commons.wikimedia.org/w/api.php'
    params = {
        'action': 'query',         # Action is query
        'format': 'json',          # Format the output as JSON
        'prop': 'imageinfo',       # Get image information
        'titles': f'File:{file_title}',  # Specify the title of the file
        'iiprop': 'timestamp'      # Get the timestamp (upload date)
    }
    response = requests.get(API_ENDPOINT, params=params)
    response.raise_for_status()
    data = response.json()
    page_id = next(iter(data['query']['pages']))
    if 'missing' in data['query']['pages'][page_id]:
        return f"File '{file_title}' does not exist on Wikimedia Commons."
    upload_date = data['query']['pages'][page_id]['imageinfo'][0]['timestamp']

    return upload_date

def get_wikipedia_articles_by_qid(qids):
    url = "https://www.wikidata.org/w/api.php"
    articles = [["item_id","wiki","url","views_30d"]]
    i = 1
    for qid in qids:
        print(f"{i}/{len(qids)} fetching {qid} from {url}")
        i = i+1
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "format": "json",
            "props": "sitelinks/urls"
        }
        response = requests.get(url, params=params)
        try:
            data = response.json()
        except:
            print(f"error getting articles for {qid} from {url}")
            #print(response.text)
        if 'entities' in data and qid in data['entities']:
            sitelinks = data['entities'][qid].get('sitelinks', {})
            for key, value in sitelinks.items():
                if 'wiki' in key:
                    language_code = key.replace('wiki', '')
                    article_url = value['url']
                    views = None
                    if "commonswiki" not in key or "voyage" not in key or "quote" not in key or "be_x_old" not in key or "news" not in key:
                        article_title = article_url.split("/")[len(article_url.split("/"))-1]
                        platform = language_code+".wikipedia"
                        views = get_wikipedia_views(article_title, platform)
                    articles.append([qid, language_code+".wikipedia.org", article_url, views])
    return articles

def get_wikipedia_views(article_title, platform, days=30):
    headers = {
        'User-Agent': 'ProjektFredrika/1.0 (robert@projektfredrika.fi)'  # Replace with your app and contact info
    }
    # Format today's date and the start date (30 days ago)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)
    end_date = end_date.strftime('%Y%m%d')
    start_date = start_date.strftime('%Y%m%d')

    # Wikipedia API endpoint for pageviews
    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{platform}/all-access/user/{article_title}/daily/{start_date}/{end_date}"
    # Make the request to the Wikipedia API
    response = requests.get(url, headers=headers)
    try:
        data = response.json()
    except:
        print("error getting views: "+url)
        #print(response.text)

    # Check if 'items' key is in the data
    if 'items' in data:
        total_views = sum(day['views'] for day in data['items'])
        print(f"{platform} {article_title} views_30d:{total_views}")
        return total_views
    else:
        print(f"No 'items' key found in the response: {url}")
        return None

def main():
    path = "./"
    filepath = path+"commons-statistik-categories.txt"
    categories = read_list_of_categories(filepath)

    results = []
    for category in categories: 
        print(f"\nStarting new category: {category}")
        files = get_files_in_category(category)
        print(f"Found {len(files)} files in {category}")
        for index, file in enumerate(files):
            avgpermonth = 0
            yearviews = None
            yearviews = get_image_views(file, start = "2022110100", end = "2023103100")
            if yearviews == None:
                print("no year")
            else: 
                if yearviews:
                    yearviews = round(yearviews)
                    avgpermonth = round(yearviews/12)
            usages = get_image_usage(file)
            uploaddate = None
            uploaddate = get_upload_date(file)
            if not usages:
                print(index, len(files), category, file)
                results.append({"category":category, "image":file, "views_year":yearviews, "avg_month": avgpermonth, "uploaddate":uploaddate})
            else: 
                for wiki, page_title in usages:
                    #print("Next", page_title)
                    user, timestamp, item_id, i = get_history_and_find_image_addition(page_title, file, wiki)
                    print(index, len(files), category, file,wiki,page_title,user,timestamp, item_id, i)
                    results.append({"category":category, "image":file, "views_year":yearviews, "avg_month": avgpermonth, "wiki":wiki, "page_title":page_title, "item_id":item_id, "user":user, "revtimestamp":timestamp, "uploaddate":uploaddate, "in_use":"True"})

    output_file1 = "commons_statistics.xlsx"
    output_file2 = "commons_statistics_with_potential.xlsx"
    df = pd.DataFrame(results)

    lang_df = pd.read_csv('lang_code.csv')
    lang_dict = dict(zip(lang_df['WP-code'], lang_df['Language']))   
    df['language_code'] = df['wiki'].str.split('.').str[0]
    df['platform'] = df['wiki'].str.split('.').str[1]
    df['language'] = df['language_code'].map(lang_dict)
    df = df.drop('language_code', axis=1)
    cols = df.columns.tolist()
    cols.insert(cols.index('wiki') + 1, cols.pop(cols.index('language')))
    df = df[cols]
    cols = df.columns.tolist()
    cols.insert(cols.index('wiki') + 1, cols.pop(cols.index('platform')))
    df = df[cols]
    df.fillna("", inplace=True)
    print(df)

    # Create a new Excel workbook
    workbook = Workbook()
    worksheet = workbook.active
    for row in dataframe_to_rows(df, index=False, header=True):
        worksheet.append(row)
    for cell in worksheet['A'][1:]:
        cell.hyperlink = "https://commons.wikimedia.org/wiki/Category:"+str(cell.value)
    for cell in worksheet['B'][1:]:
        cell.hyperlink = "https://commons.wikimedia.org/wiki/"+str(cell.value)
    for index, cell in enumerate(worksheet['H'][1:], start=1):
        domain = worksheet['E'][index].value
        if domain != "":
            cell.hyperlink = f"https://{domain}/wiki/"+str(cell.value)
    for cell in worksheet['J'][1:]:
        if cell.value != "":
            cell.hyperlink = "https://wikidata.wikiscan.org/?menu=userstats&user="+str(cell.value)
    # Save the workbook to an XLSX file
    print("saving statistics to worksheet")
    workbook.save(output_file1)
    print("done")


    qids = df['item_id'].unique().tolist()
    print(qids)
    rows = get_wikipedia_articles_by_qid(qids)
    dfarticles = pd.DataFrame(rows[1:], columns=rows[0])
    print(dfarticles)
    merged_df = pd.merge(df[df['in_use'] == "True"], dfarticles, on=['item_id', 'wiki'], how='outer') # [dfarticles['wiki'].isin(['sv.wikipedia.org', 'fi.wikipedia.org', 'en.wikipedia.org'])]
    merged_df = merged_df.sort_values(by=['item_id','image','category'])
    merged_df['category'] = merged_df['category'].fillna(method='ffill')
    merged_df['image'] = merged_df['image'].fillna(method='ffill')
    merged_df['in_use'] = merged_df['in_use'].fillna("False")

    df = merged_df
    df = df.sort_values(by=['category','image','in_use'], ascending=[True, True, False])
    print(df)

    # Create a new Excel workbook
    workbook = Workbook()
    worksheet = workbook.active
    for row in dataframe_to_rows(df, index=False, header=True):
        worksheet.append(row)
    print("A")
    for cell in worksheet['A'][1:]:
        cell.hyperlink = "https://commons.wikimedia.org/wiki/Category:"+str(cell.value)
    print("B")
    for cell in worksheet['B'][1:]:
        cell.hyperlink = "https://commons.wikimedia.org/wiki/"+str(cell.value)
    #print("H")
    #for index, cell in enumerate(worksheet['H'][1:], start=1):
    #    domain = worksheet['E'][index].value
    #    if domain != "":
    #        cell.hyperlink = f"https://{domain}/wiki/"+str(cell.value)
    print("J")
    for cell in worksheet['J'][1:]:
        if cell.value != "":
            cell.hyperlink = "https://wikidata.wikiscan.org/?menu=userstats&user="+str(cell.value)
    print("N")
    for cell in worksheet['N'][1:]:
        cell.hyperlink = str(cell.value)
    # Save the workbook to an XLSX file
    print("saving statistics with potential articles to worksheet")
    workbook.save(output_file2)
    print("done")

if __name__ == "__main__":
    main()