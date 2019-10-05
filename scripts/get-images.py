import requests
from pathlib import Path


def main():
    dir = Path('..') / 'bilder'
    if not dir.exists():
        dir.mkdir()
    elif not dir.is_dir():
        print("Cannot create directory bilder, exiting...")
    with open(Path('..') / 'bilder.txt') as f:
        for url in f.readlines():
            download_image(url)


def download_image(url):
    img_name = url.split('/')[-1]
    img_data = requests.get(url).content
    with open(Path('..') / 'bilder' / img_name, 'wb') as f:
        f.write(img_data)


if __name__ == '__main__':
    main()
