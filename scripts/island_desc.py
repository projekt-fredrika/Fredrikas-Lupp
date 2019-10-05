import csv
from heapq import heappush, heappop
from pathlib import Path
from itertools import combinations
from math import radians, sin, cos, asin, sqrt, degrees, atan2

islands = {}


def make_island_dict():
    # No need to fill dict if it already has been filled
    if islands:
        return islands
    support_islands = {}
    with open(Path('..') / 'stödpunkter.csv') as f:
        rows = csv.reader(f)
        for name, _, lat, lon, *_ in rows:
            support_islands[name] = (float(lat), float(lon))
    with open(Path('..') / 'Öar i Nagu.csv') as f:
        rows = csv.reader(f)
        for page, lat, lon, name, area, length, *_ in rows:
            islands[page] = {'name': name,
                             'cords': (float(lat), float(lon)),
                             'area': float(area) if area else 0.0,
                             'length': float(length) if length else 0.0,
                             'neighbours': [],
                             'support_islands': []}
    for pair in combinations(islands.keys(), 2):
        island1, island2 = pair
        dist = distance(*islands[island1]['cords'], *islands[island2]['cords'])
        heappush(islands[island1]['neighbours'], (dist, islands[island2]['name']))
        heappush(islands[island2]['neighbours'], (dist, islands[island1]['name']))

    for island in islands.keys():
        for supp_island, supp_cords in support_islands.items():
            dist, dir = distance_and_direction(*islands[island]['cords'], *supp_cords)
            heappush(islands[island]['support_islands'], (dist, dir, supp_island))

    return islands


def get_island_dict():
    return make_island_dict()


def island_desc(page):
    make_island_dict()
    name = islands[page]['name']
    lat, lon = islands[page]['cords']
    area = islands[page]['area']
    sup1, sup2 = islands[page]['support_islands'][:2]
    dist1, dir1, sup1 = sup1
    dist2, dir2, sup2 = sup2
    close1, close2, close3 = islands[page]['neighbours'][:3]
    dist_c1, close1 = close1
    dist_c2, close2 = close2
    dist_c3, close3 = close3
    kyrk_dist, kyrk_dir = distance_and_direction(60.194, 21.906, lat, lon)
    ret_str = (f'<artikel titel="{name}">'
               f'<b> {name}</b>, {lat:.4f}°N, {lon:.4f}°Ö, {area * 100:.1f} ha stor ö '
               f'{dist1:.0f} km {dir1} om <i>{sup1}</i>, '
               f'{dist2:.0f} km {dir2} om <i>{sup2}</i>, '
               f'{kyrk_dist:.0f} km {kyrk_dir} om <i>Kyrkbacken</i>.'
               f'\nGrannöar: {close1}, {close2}, {close3}.</artikel>')
    return ret_str


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
    dirs = ['N', 'NÖ', 'Ö', 'SÖ', 'S', 'SV', 'V', 'NV']
    dir_idx = int((bearing + 22.5) / 45 - 0.02)
    return km, dirs[dir_idx % 8]


def distance(lat1, lon1, lat2, lon2):
    """in km using haversine formula"""
    # convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # haversine formula
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    a = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    c = 2 * asin(sqrt(a))

    # 6367 km is the radius of the Earth
    km = 6367 * c
    return km
