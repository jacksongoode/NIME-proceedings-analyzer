# This file is part of the NIME Proceedings Analyzer (NIME PA)
# Copyright (C) 2023 Jackson Goode, Stefano Fasciani

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

# Native
import os
import csv
import socket
import requests
from collections import Counter

# External
import pandas as pd
import numpy as np
import re
from geopy.distance import geodesic
from tqdm import tqdm

# Helper
import pa_print

def csv_save(bib_db):
    ''' Saves current dataframe into a csv

    :database from constructed from bibtex file
    '''
    df = pd.DataFrame(bib_db)
    df = df.sort_index(axis=1)
    df.to_csv('./output/export.csv', index=False, encoding='utf-8')

def calculate_carbon(pub):
    ''' Calculate the carbon emissions from travel

    :publication (article) from database
    '''
    author_count = pub['author count']

    pa_print.tprint('\nCalculating carbon footprint...')
    for author in range(author_count):
        if pub['author location info'][author] != 'N/A':
            distance = geodesic(pub['author location info'][author][2], pub['conference location info'][0][2]).km
            pub['author distances'].append(distance)

            # * Calculate C02 emissions, more details here: https://github.com/milankl/CarbonFootprintAGU
            carbon = 0.0 # kgCO2e

            if distance < 400:      # bus / train / car at 60gCO2e / km / person
                carbon = distance * 2 * 0.06
            elif distance < 1500:   # short flight at 200gCO2e / km / person
                carbon = distance * 2 * 0.2
            elif distance < 8000:   # long flight at 250gCO2e / km / person
                carbon = distance * 2 * 0.25
            else:                   # super long flight at 300gCO2e / km / person
                carbon = distance * 2 * 0.3

            pub['author footprints'].append(carbon / 1000)
            pa_print.tprint(f'✓ - CO2 emissions for author {int(author + 1)}: {(carbon / 1000):.3f} tCO2e')
        else:
            pub['author distances'].append('N/A')
            pub['author footprints'].append('N/A')

def fill_empty(pub):
    '''In case there is an errored pdf or grobid doc, fill in the fields with 'N/A'

    :publication (article) from database
    '''
    author_count = pub['author count']

    # * citation numer and conference location info should be filled regardless
    # * author distances, author footprints, author loc queries, and author location info are filled elsewhere - issue #10
    # ? even if file is corrupt there may be some relevant info
    for entry in ['author infos', 'grobid addresses', 'grobid author names', 'grobid author unis', 'grobid emails', 'grobid organisations', 'text author unis']:
        pub[entry] = ['N/A' for author in range(author_count)]

def doc_check(doc, pub, type):
    ''' Check for common decoding errors (does not catch all) # ! more intelligent method?

    :document from text extraction (miner) or xml extraction (grobid)
    :publication (article) from database
    :type of doc (either 'text' or 'grobid')
    '''
    errored = False

    alphas = re.compile('[^a-zA-Z]')
    doc_alphas = alphas.sub('', doc)
    if len(doc) > 2 * len(doc_alphas) : # more symbols than 2x letters
        pub[f'{type} non alpha'] = 'X'
        pa_print.tprint('\nFile was not decoded well - non-alpha')
        errored = True

    cids = re.compile(r'\(cid:[0-9]+\)')
    doc_cidless = cids.sub('', doc, re.M) # when font cannot be decoded, (cid:#) is returned, remove these
    if len(doc) > 2 * len(doc_cidless): # if most of content was undecodable, skip
        pub[f'{type} poor decoding'] = 'X'
        pa_print.tprint('\nFile was not decoded well - cid: present')
        errored = True

    return errored

def doc_quality(doc, pub, type):
    ''' Check for document quality

    :document from text extraction (miner) or xml extraction (grobid)
    :publication (article) from database
    :type of doc (either 'text' or 'grobid')
    '''
    errored = False

    if not (doc and doc.strip()): # if doc is clearly errored or empty
        fill_empty(pub)
        pub[f'{type} fail'] = 'X'
        errored = True
    else:
        errored = doc_check(doc, pub, type) # issues with decoding

    return errored

def try_index(something, index, fail):
    try:
        return eval(f'{something}{index}')
    except:
        return fail

def import_config(filepath):
    ''' Imports a custom configuration for filter words and years

    :filepath the file path
    '''
    user_config = pd.read_csv(filepath, header=0, delimiter=',')
    user_config = user_config.fillna('')

    keywords = []
    ignore_words = []
    merge_words = []
    selected_years = []

    for config_tuple in user_config.itertuples(index=False):
        if config_tuple[0] == 'keywords': # single list
            for i in config_tuple[1:]:
                keywords.append(i)
        elif config_tuple[0] == 'ignore': # single list
            for i in config_tuple[1:]:
                ignore_words.append(i)
        elif config_tuple[0] == 'merge': # list of lists
            merge_group = list(filter(None, config_tuple[1:]))
            merge_words.append(merge_group)
        elif config_tuple[0] == 'years': # single list
            year_num = [i for i in config_tuple if i != '']
            if len(year_num) == 2:
                selected_years.append(str(int(config_tuple[1])))
            else:
                year_span = int(config_tuple[2]) - int(config_tuple[1])
                for i in range(year_span + 1):
                    selected_years.append(str(int(config_tuple[1]) + i))

    keywords = list(filter(None, keywords))
    ignore_words = list(filter(None, ignore_words))

    pa_print.tprint('\nParameters from custom.csv:')
    if selected_years:
        pa_print.tprint(f'Selected years: {selected_years}')
    if keywords:
        pa_print.tprint(f'Search words: {keywords}')
    if ignore_words:
        pa_print.tprint(f'Ignored words: {ignore_words}')
    if merge_words:
        pa_print.tprint(f'Merged words: {merge_words}')

    return (keywords, ignore_words, merge_words, selected_years)

def boolify(ans, default=False):
    ''' Takes a question letter and converts it to a bool

    :ans as a letter (ex. y, b)
    :default bool if user types something else
    '''
    if ans in ['Y','y','yes']:
        ans = True
    elif ans in ['N','n','no']:
        ans = False
    else:
        ans = default
    return ans

def post_processing(pub):
    col_countries, col_continents, col_institutions = [], [], []
    empty = [float('nan'), 'N/A']
    full_text = ''

    for author in range(pub['author count']):

        # Countries and continents
        countries = [try_index(country, '[1][0]', 'N/A') for country in pub['author location info']]
        for i, n in enumerate(countries):
            if 'Korea' in n:
                countries[i] = 'Republic of Korea'
            elif 'The Netherlands' in n:
                countries[i] = 'Netherlands'

        continents = [try_index(continent, '[1][1]', 'N/A') for continent in pub['author location info']]

    pub['countries'] = countries
    pub['continents'] = continents

    # Check for unis and organisations
    institutions = []
    for _, (uni, org) in enumerate(zip(pub['grobid author unis'], pub['grobid organisations'])):
        if uni in empty: # if uni is absent and there is an org present for that index
            institutions.append(org)
        else:
            institutions.append(', '.join(uni)) # make unique string from (uni, location)
    pub['institutions'] = institutions # this is a union list to derive location using uni or organisation

    # Iterate through article and get raw text
    if pub['puppub']:
        file_name = f"nime{pub['year']}_{pub['articleno']}"
    else:
        file_name = pub['url'].split('/')[-1].split('.')[0]

    grob_text_file = f'./cache/text/grobid/grob_{file_name}.txt'

    if os.path.isfile(grob_text_file): # check if txt already exists
        with open(grob_text_file, 'r') as f:
            full_text = f.read()

    if len(full_text.split(' ')) < 10: # body text missing in grobid file - check for miner
        miner_text_file = f'./cache/text/miner/miner_{file_name}.txt'

        if os.path.isfile(grob_text_file): # check if txt already exists
            with open(miner_text_file, 'r') as f:
                full_text = f.read()

    # adding word count
    pub['word count'] = len(full_text.split())
