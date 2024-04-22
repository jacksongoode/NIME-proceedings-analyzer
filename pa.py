# NIME Proceedings Analyzer (NIME PA)
# Copyright (C) 2024 Jackson Goode, Stefano Fasciani

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
import sys

from tqdm import tqdm

import pa_print
from pa_extract import extract_author_info, extract_grobid, extract_text
from pa_load import check_xml, extract_bibtex, load_bibtex, load_unidomains, prep
from pa_request import request_location, request_scholar, request_uni
from pa_utils import calculate_carbon, csv_save, doc_quality, post_processing

if sys.version_info < (3, 11):
    print("Please upgrade Python to version 3.11.0 or higher")
    sys.exit()

# Variables/paths
bibtex_path = os.getcwd() + "/cache/bibtex/nime_papers.bib"
unidomains_path = os.getcwd() + "/cache/json/unidomains.json"
pubpub_years = ["2021", "2022"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze a publication given a BibTeX and directory of pdf documents"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="prints out operations",
    )
    parser.add_argument(
        "-c",
        "--citations",
        action="store_true",
        default=False,
        help="bypass cache to retrieve new citations",
    )
    parser.add_argument(
        "-g",
        "--grobid",
        action="store_true",
        default=False,
        help="forces repopulation of Grobid files",
    )
    parser.add_argument(
        "-r", "--redo", action="store_true", default=False, help="deletes cache"
    )
    parser.add_argument(
        "-n",
        "--nime",
        action="store_true",
        default=False,
        help="uses NIME based corrections",
    )
    parser.add_argument(
        "-p",
        "--pdf",
        action="store_true",
        default=False,
        help="use manually downloaded pdf for PubPub publications",
    )
    parser.add_argument(
        "-ock", "--ockey", type=str, default="", help="OpenCage Geocoding API key"
    )
    parser.add_argument(
        "-ssk", "--sskey", type=str, default="", help="Semantic Scholar API key"
    )
    parser.add_argument(
        "-s",
        "--sleep",
        type=float,
        default=3,
        help="sleep time (sec) between Semantic Scholar API calls",
    )

    args = parser.parse_args()

    # * Set global print command
    pa_print.init(args)

    # * Print notice
    pa_print.lprint()

    # * Prepare cache, etc.
    prep(args)

    # * Load database for email handle to uni matching
    unidomains = load_unidomains(unidomains_path)

    # * Load and extract BibTeX
    bib_db = load_bibtex(bibtex_path)
    bib_db = extract_bibtex(bib_db, args)

    # * Loop here for Grobid/PDF population
    if args.grobid:
        check_xml(bib_db, args, False, True, pubpub_years)

    # * Parse data through pdfs
    print("\nExtracting and parsing publication data...")
    iterator = tqdm(bib_db)
    for _, pub in enumerate(iterator):
        pa_print.tprint(f"\n--- Now on: {pub['title']} ---")

        # check if on PubPub
        if pub["year"] not in pubpub_years:
            pub["puppub"] = False
        else:
            pub["puppub"] = True

        # Extract text from pdf if not PubPub or if forced to manually downloaded pdf
        if pub["puppub"] == False or args.pdf:
            doc = extract_text(pub)
            errored = doc_quality(doc, pub, "text")  # check for errors

            # Only extract header meta-data if not errored
            if not errored:
                author_info = extract_author_info(doc, pub)
            else:
                author_info = []
        else:
            author_info = []

        # Extract doc from Grobid
        doc = extract_grobid(pub, bib_db, iterator, args, pubpub_years)
        doc_quality(doc, pub, "grobid")

        # Get university from various sources
        request_uni(unidomains, author_info, args, pub)

        # Get location from API and query
        request_location(author_info, args, pub)

        # Use location for footprint calculation
        calculate_carbon(pub)

        # Get citations from Semantic Scholar
        request_scholar(pub, args)

        # Post processing modifications
        post_processing(pub, args)

        # Save for every paper
        csv_save(bib_db)
