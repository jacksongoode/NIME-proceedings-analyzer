# This file is part of the NIME Proceedings Analyzer (NIME PA)
# Copyright (C) 2026 Jackson Goode, Stefano Fasciani

# The NIME PA is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# The NIME PA is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# If you use the NIME Proceedings Analyzer or any part of it in any program or
# publication, please acknowledge its authors by adding a reference to:

# J. Goode, S. Fasciani, A Toolkit for the Analysis of the NIME Proceedings
# Archive, in 2022 International Conference on New Interfaces for
# Musical Expression, Auckland, New Zealand, 2022.

import argparse
import os
import pickle
import sys
import warnings
import datetime

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy.interpolate import UnivariateSpline

import pa_print
from pa_utils import import_config

if sys.version_info < (3, 11):
    print("Please upgrade Python to version 3.11.0 or higher")
    sys.exit()

warnings.filterwarnings("ignore", category=DeprecationWarning)


grobid_text_src = "./cache/text/grobid/"
lda_src = "./cache/lda/"
num_topics = 5


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A script for querying search terms occurrence over time"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="prints out analysis process and results",
    )
    args = parser.parse_args()

    # Sets global print command
    pa_print.init(args)

    # Print notice
    pa_print.lprint()

    keywords, _, _, selected_years = import_config(
        "./resources/custom.csv"
    )  # ignore and merge words already processed
    if len(keywords) == 0:
        print("No keywords found! Please add keywords in ./resources/custom.csv.")
        sys.exit()

    if len(selected_years) != 0:
        year_range = list(map(int, selected_years))
        year_start, year_end = min(year_range), max(year_range) + 1
    else:
        year_start  = 2001
        year_end = datetime.date.today().year - 1
        year_range = range(year_start, year_end)

    print(f"Searching for {keywords} in years {year_range}")

    print("\nLoading bodies, dict, corpus, and model...")
    processed_bodies = pickle.load(open(lda_src + "bodies.pkl", "rb"))

    # Create list to mark each text with year (will be linked to corpus values)
    year_list = []
    for i in os.listdir(grobid_text_src):
        if i.startswith("grob_"):
            name = i.lower().split("grob_nime")[-1]
            year = int(name.split("_")[0])
            if (
                year < 2000
            ):  # handle PubPub grobid named only with last 2 digits of the year
                year = year + 2000
            year_list.append((year, name))

    keyword_frequency = pd.DataFrame(index=year_range, columns=keywords)

    searched_words = dict()
    year_counts = dict()
    for i in year_range:
        searched_words[i] = {}
        year_counts[i] = 0

    for year, doc in zip(year_list, processed_bodies):
        year = year[0]
        if year in year_range:
            for term in keywords:
                if searched_words[year].get(term):
                    searched_words[year][term] += doc.count(
                        term
                    )  # update year total with current count
                else:  # initial entry
                    searched_words[year].update({term: doc.count(term)})

            year_counts[year] += len(doc)  # get total words/year

    for year, search in searched_words.items():
        for term in keywords:
            search[term] = search[term] / year_counts[year]
            keyword_frequency.at[year, term] = search[term]

    # * Show searched words
    plt.figure(figsize=(20, 10))

    x = [year for year in searched_words.keys()]
    for word in keywords:
        y = [search[word] for search in searched_words.values()]
        plt.scatter(x, y, label=word)

        # Spline
        s = UnivariateSpline(x, y, s=5)
        xs = np.linspace(year_start, year_end - 1, 100)
        ys = s(xs)
        plt.plot(xs, ys, label=f"Spline for {word}")

    plt.legend()
    plt.xlabel("Year")
    plt.ylabel("Frequency of Keyword within Paper")
    plt.title("Frequency of Keyword over Publication Year")
    plt.savefig("./output/keyword_occurrence.png")

    with pd.ExcelWriter("./output/keyword_occurrence.xlsx") as writer:
        keyword_frequency.to_excel(writer, sheet_name="Keyword Occurrence", header=True)
