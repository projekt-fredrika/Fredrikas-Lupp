"""
Analyzes and plots graph of views, quality and length based on saved json-dumps
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.table import table, Table
from matplotlib.axes import Axes

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Tuple, List, Union


def load_data(lang, cat: str) -> List:
    """Load all json files for the selected category and return list of all the data"""
    data_path = Path('./json')
    data_paths = list(data_path.glob(f"*/{cat.replace(' ','_')}.json"))
    data_paths.sort()
    print(f"Analyserar kategori {cat} för språket ({lang}), hittade filerna:")
    [print(str(p)) for p in data_paths]
    # data_dicts = []
    try:
        data_dicts = [json.load(open(str(p))) for p in data_paths]
    except FileNotFoundError as fe:
        print("Hittade inte filen" + str(fe.args))
        sys.exit()
    return data_dicts


def analyze_data(d_dict: List, label: str, lang: str) -> List:
    """Extract all data of 'label' from data and return list of values and change"""
    stat_list = []
    for d in d_dict:
        if label == 'dates':
            stat_list.append(datetime.strptime(d['stats']['scraped'][:10], "%Y-%m-%d"))
        elif label == 'pages':
            stat_list.append(len([p for p in d['pages'] if f"({lang})" in p]))
        buff = []
        for page in d['pages']:
            if f"({lang})" not in page:
                continue
            dict_key = ''
            if label == 'pages' or label == 'dates':
                break
            elif label == 'length':
                dict_key = f"len_{lang}"
            elif label == 'quality':
                dict_key = f"quality"
            elif label == 'views':
                dict_key = f"pageviews_{lang}"
            buff.append(int(d['pages'][page]['stats'][dict_key]))
        if buff:
            stat_list.append(sum(buff))
    if label == 'dates':
        return stat_list
    change = stat_list[-1] - stat_list[0]
    avg = stat_list[-1] // len([p for p in d_dict[-1]['pages'] if f"({lang})" in p])
    change_p = change / stat_list[0] * 100
    change = f"+{change:,}".replace(',', ' ') if change > 0 else str(change)
    return stat_list + [change, f"{change_p:1.0f}%", f"{avg:,}".replace(',', ' ')]


def plot_and_fmt(start_date, stop_date, cat, lang, views, quality, length, dates) -> Tuple[Axes, Axes]:
    """Create plot on a figure same size as a A4 paper, with data from views, qualitym lenght and dates"""
    fig, ax = plt.subplots(figsize=(17, 22))

    title = f"Kategori:{cat} ({lang}) under Fredrikas Lupp\nför tidsperioden {start_date} --- {stop_date}"
    plt.title(title, fontsize=24, pad=30)
    ax.bar(dates, views[:-3], width=-1, edgecolor='k', color='salmon', label='Views', align='edge')
    ylabel = "Total Views"
    if lang == 'sv':
        ylabel = "Total Views and Quality"
        ax.bar(dates, quality[:-3], width=1, edgecolor='k', color='darkred', label='Quality', align='edge')
    ax.set_ylabel(ylabel, color='r')
    ax.tick_params('y', labelcolor='r')
    ax.tick_params('x', which='minor', labelsize=6)
    ax.tick_params('x', which='major', length=5, width=2, pad=9)
    ax.set_xlabel('Date')
    ax2 = ax.twinx()
    ax2.plot(dates, length[:-3], 'bo-', label='Length')
    ax2.set_ylabel('Total Length in characters', color='b')
    ax2.tick_params('y', labelcolor='b')

    fmt_labels_and_lims(length, quality, views, lang, ax, ax2)
    fig.autofmt_xdate(which='both')

    return ax, ax2


def fmt_labels_and_lims(length, quality, views, lang, ax: Axes, ax2: Axes) -> None:
    """Format labels and limits on axes ax and ax2 to fit data"""

    # setup x-axis dates
    months = mdates.MonthLocator()
    days = mdates.DayLocator()
    month_fmt = mdates.DateFormatter('%B')
    day_fmt = mdates.DateFormatter('%-d.%-m')

    # format the date labels
    ax.xaxis.set_major_locator(months)
    ax.xaxis.set_major_formatter(month_fmt)
    ax.xaxis.set_minor_locator(days)
    ax.xaxis.set_minor_formatter(day_fmt)

    # caculate limits based on data
    ax_values = views[:-3] + quality[:-3] if lang == 'sv' else views[:-3]
    ax_max = int(max(ax_values))
    ax_min = int(min(ax_values))
    ax2_max = int(max(length[:-3]))
    ax2_min = int(min(length[:-3]))
    ax_lim_max = (ax_max * 1.1) + 100
    # ax_lim_max = ax_max + int((ax_max - ax_min) * 0.3) + 5
    # ax_lim_min = ax_min - int((ax_max - ax_min) * 0.2) - 5
    # ax2_lim_max = ax2_max + int((ax2_max - ax2_min) * 0.3) + 5
    ax2_lim_max = (ax2_max * 1.2) + 100
    # ax2_lim_min = ax2_min - int((ax2_max - ax2_min) * 0.2) - 5
    # set the limits on y-axis
    ax.set_ylim(0, ax_lim_max)
    ax2.set_ylim(0, ax2_lim_max)

    # format x and y data for interactiva metplotlib plots
    def view(x: Union[str, int, float]) -> str:
        return '{:1.0f} length'.format(x)

    ax2.format_xdata = mdates.DateFormatter('%-d %B %Y')
    ax.format_ydata = view
    ax2.format_ydata = view

    # add legend to plot
    plt.legend()
    ax.legend(loc=2)
    ax2.legend(loc=1)


def add_table(length, quality, views, pages, dates, lang, ax: Axes) -> Table:
    """Add a table to figure aunder the plot to display values from all input files"""
    table_height = 4 if lang == 'sv' else 3
    table_width = len(length)
    table_text = [[f"{x:,}".replace(',',  ' ') for x in length[:-3]] + length[-3:],
                  [f"{x:,}".replace(',', ' ') for x in views[:-3]] + views[-3:],
                  [f"{x:,}".replace(',', ' ') for x in pages[:-3]] + pages[-3:]]
    row_labels = ['Length', 'Views', 'Pages']
    if lang == 'sv':
        table_text.insert(1, [f"{x:,}".replace(',',  ' ') for x in quality[:-3]] + quality[-3:])
        row_labels.insert(1, 'Quality')

    data_table = table(ax, cellText=table_text,
                       rowLabels=row_labels,
                       colLabels=[d.strftime('%-d %b %Y') for d in dates] +
                                 ['    Change    ', 'Change in %', 'Average / page'],
                       bbox=[0, -0.7, 0.9, 0.5],
                       loc='bottom')
    data_table[table_height, len(length) - 1].get_text().set_text('-')

    for col in range(table_width):
        data_table[0, col].set_lw(3.0)
    for row in range(1, table_height + 1):
        data_table[row, -1].set_lw(3.0)
    data_table.auto_set_column_width(range(table_width))
    for row in range(1, table_height + 1):
        col_nr = table_width - 3
        cell_text = data_table[row, col_nr].get_text()
        if '+' in cell_text.get_text():
            data_table[row, col_nr].set_facecolor('lightgreen')
            data_table[row, col_nr + 1].set_facecolor('lightgreen')
            data_table[row, col_nr].set_fill(True)
            data_table[row, col_nr + 1].set_fill(True)
        elif '-' in cell_text.get_text():
            data_table[row, col_nr].set_facecolor('lightcoral')
            data_table[row, col_nr + 1].set_facecolor('lightcoral')
            data_table[row, col_nr].set_fill(True)
            data_table[row, col_nr + 1].set_fill(True)
    return data_table


def save_plot(cat, lang):
    """Load data, plot and save the file in the analysis/ directory"""

    data = load_data(lang, cat)
    # exit script if only one file found
    if len(data) < 2:
        print("Kan inte producera analys av endast en fil, avbryter")
        return
    start_date = data[0]['stats']['scraped'][:10]
    stop_date = data[-1]['stats']['scraped'][:10]
    views = analyze_data(data, 'views', lang)
    quality = analyze_data(data, 'quality', lang)
    length = analyze_data(data, 'length', lang)
    pages = analyze_data(data, 'pages', lang)
    dates = analyze_data(data, 'dates', lang)

    axis, axis2 = plot_and_fmt(start_date, stop_date, cat, lang, views, quality, length, dates)
    add_table(length, quality, views, pages, dates, lang, axis)
    footer = "Wikipedia-analys utförd med Fredrkas Lupp av projekt Projekt Fredrika r.f. www.projektfredrika.fi"
    plt.figtext(0.1, 0.02, footer, fontdict={'color': 'darkgreen'})
    # fix plot to upper half of page and text below
    plt.subplots_adjust(bottom=0.5, top=0.9)

    outdir = 'analysis/'
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    plot_name = f"{outdir}{cat}_{lang}_plot.pdf"

    plt.savefig(plot_name)
    print(f"Sparade filen {plot_name}")
    return


if __name__ == '__main__':
    cnt_args = len(sys.argv)
    category = 'None' if cnt_args < 2 else sys.argv[1]
    language = 'sv' if cnt_args < 3 else sys.argv[2]
    save_plot(category, language)
    if cnt_args > 3:
        # debugging to show plot
        plt.show()
    sys.exit()
