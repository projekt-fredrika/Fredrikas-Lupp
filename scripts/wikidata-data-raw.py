# coding: utf-8

import requests
import httpx
import asyncio
import json
import csv


url = 'https://query.wikidata.org/sparql'
query = """SELECT ?personLabel ?sexLabel ?birth ?placeLabel ?occupationLabel WHERE {
  ?person wdt:P172 wd:Q726673.
  ?person wdt:P21  ?sex.
  ?person wdt:P569 ?birth.
  ?person wdt:P19  ?place.
  ?person wdt:P106 ?occupation.
  OPTIONAL {
    ?artikel schema:about ?person.
    ?artikel schema:inLanguage "sv".
    ?artikel schema:isPartOf <https://sv.wikipedia.org/>.
  }
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "[AUTO_LANGUAGE],sv".
  }
}"""

print(f"Querying wikidata...")
r = requests.get(url, params={'format': 'json', 'query': query})
data = r.json()
res = []
names = set()
print(f"Got response from wikidata! Parsing...")
print(data['results']['bindings'][:10])

for person in data['results']['bindings']:
    try:
        names.add(person['personLabel']['value'])
        p = {
            'namn': person['personLabel']['value'],
            'kön': person['sexLabel']['value'],
            'arbete': person['occupationLabel']['value'],
            'tid': str(int(person['birth']['value'][:3]) * 10 + 30)[:2] +
            "00-tal",
            'plats': person['placeLabel']['value']
        }
        res.append(p)
    except KeyError as e:
        print(f"Could not add {person['personLabel']['value']},"
              f" not found key: {e}")

print(f"Parsed {len(res)} data points.")


async def get_stat(title, stat, client, res_dict):
    if stat not in ['pageviews', 'pagelength']:
        print("get_stat() only supports pageviews and pagelength")
        return 0
    if stat == 'pagelength':
        r = await client.get('https://sv.wikipedia.org/w/api.php?',
                             params={'action': 'query',
                                     'format': 'json',
                                     'titles': title,
                                     'prop': 'revisions',
                                     'rvprop': 'size'})
        try:
            res_pages = list(r.json()['query']['pages'].values())
            res = res_pages[0]['revisions'][0]['size']
            res_dict['sidlängd'] = res
        except KeyError as e:
            print(f"Error with {e} for page {title}: {r.json()}")
        except json.decoder.JSONDecodeError as e:
            print(f"Problem with json data for {title}: {e}")
    else:
        r = await client.get('https://sv.wikipedia.org/w/api.php?',
                             params={'action': 'query',
                                     'format': 'json',
                                     'titles': title,
                                     'prop': 'pageviews'})
        try:
            res_pages = list(r.json()['query']['pages'].values())
            pageviews = res_pages[0]['pageviews'].values()
            res = sum([int(x) for x in pageviews if x and str(x).isdigit()])
            res_dict['color'] = get_color(res)
            res_dict['visningar'] = res
        except KeyError as e:
            print(f"Error with {e} for page {title}: {r.json()}")
        except json.decoder.JSONDecodeError as e:
            print(f"Problem with json data: {e}")


async def get_stats():
    tasks = []
    async with httpx.AsyncClient(timeout=None) as client:
        for p in res:
            tasks.append(get_stat(p['namn'], 'pageviews', client, p))
            tasks.append(get_stat(p['namn'], 'pagelength', client, p))
        await asyncio.gather(*tasks)


def get_color(views):
    if views < 1:
        return '#ff0000'
    elif views < 5:
        return '#ff3300'
    elif views < 10:
        return '#ff66000'
    elif views < 20:
        return '#ff99000'
    elif views < 50:
        return '#ffcc000'
    elif views < 100:
        return '#ffff000'
    elif views < 200:
        return '#ccff000'
    elif views < 500:
        return '#99ff000'
    elif views < 1000:
        return '#66ff000'
    elif views < 2000:
        return '#33ff000'
    elif views < 5000:
        return '#00ff000'


print(f"Adding stats to data points... This may take a while...")
asyncio.run(get_stats())

print(f"Rretrieved all data!")


print(f"Saving data...")

with open('finsvepeople.json', 'w') as f:
    f.write(json.dumps(res))

with open('finlandssvenskar.csv', 'w') as f:
    writer = csv.writer(f)
    for p in res:
        writer.writerow((p['namn'], p['kön'],
                         p['arbete'], p['tid'],
                         p['plats'],
                         p.get('visningar', 0),
                         p.get('sidlängd', 0)))
print(f"Program done!")
