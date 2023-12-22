# This file is part of the NIME Proceedings Analyzer (NIME PA)
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

# Native
import sys
if sys.version_info < (3, 11):
    print("Please upgrade Python to version 3.11.0 or higher")
    sys.exit()
import os
from os import path
import argparse
import ast
import collections
from itertools import cycle, chain

# External
import gensim
import unidecode
import re
import pandas as pd
from pandas import DataFrame
import pickle
import numpy as np
import datetime
from scipy.optimize import curve_fit
from matplotlib import pyplot as plt
import matplotlib.cm as cm
from sklearn.manifold import TSNE


import nltk
nltk.download('punkt', download_dir='./cache/nltk_data', quiet=True)
nltk.download('wordnet', download_dir='./cache/nltk_data', quiet=True)
nltk.download('omw-1.4', download_dir='./cache/nltk_data', quiet=True)
nltk.data.path.append('./cache/nltk_data/')

# Helper
import pa_print
from pa_utils import try_index, import_config, boolify
from pa_extract import clean_text

def lotka_law(x, n, c):
    return c / np.power(x, n)

def is_not_nan(num):
    return num == num

def load_bib_csv(filepath, selectedyears):

    if os.path.isfile('./cache/df/cleaned_bib_df.obj'):
        bib_df = pd.read_pickle('./cache/df/cleaned_bib_df.obj')
        return bib_df

    # TODO: This may not be the best solution available
    generic = lambda x: ast.literal_eval(x)
    conv = {'author distances': generic,
            'author footprints': generic,
            'author genders': generic,
            'author genders 2': generic,
            'author loc queries': generic,
            'author location info': generic,
            'author names': generic,
            'conference location info': generic,
            'grobid addresses': generic,
            'grobid author names': generic,
            'grobid author unis': generic,
            'grobid emails': generic,
            'grobid organisations': generic,
            'text author unis': generic,
            'countries': generic,
            'continents': generic,
            'institutions': generic,
            'scholar authors id': generic}

    try: # accommodate regional delimiters
        bib_df = pd.read_csv(filepath, converters=conv)
    except:
        bib_df = pd.read_csv(filepath, converters=conv, sep=';')

    #remove years not included in custom.csv_save
    if selectedyears:
        selectedyears = [int(i) for i in selectedyears]
        bib_df = bib_df[bib_df['year'].isin(selectedyears)]

    # Convert 'N/A' to NaN so pandas parser will ignore
    bib_df['author footprints'] = [pd.to_numeric(footprints, errors='coerce') for footprints in bib_df['author footprints']]
    bib_df['author distances'] = [pd.to_numeric(distances, errors='coerce') for distances in bib_df['author distances']]
    
    # Convert dicts imported as string by pandas read_csv
    bib_df['scholar embedding'] = [ast.literal_eval(embedding) if is_not_nan(embedding) else dict() for embedding in bib_df['scholar embedding']]
    bib_df['scholar tldr'] = [ast.literal_eval(tldr) if is_not_nan(tldr) else dict() for tldr in bib_df['scholar tldr']]

    # Convert lists of dicts imported as string by pandas read_csv 
    bib_df['scholar references'] = [ast.literal_eval(references) if is_not_nan(references) else list() for references in bib_df['scholar references']]
    bib_df['scholar citations'] = [ast.literal_eval(citations) if is_not_nan(citations) else list() for citations in bib_df['scholar citations']]
    bib_df['scholar field of study'] = [ast.literal_eval(references) if is_not_nan(references) else list() for references in bib_df['scholar field of study']]
    bib_df['scholar publication venue'] = [ast.literal_eval(citations) if is_not_nan(citations) else list() for citations in bib_df['scholar publication venue']]
    bib_df['scholar publication type'] = [ast.literal_eval(citations) if is_not_nan(citations) else list() for citations in bib_df['scholar publication type']]

    bib_df['scholar citation count not-NIME'] = 0

    for index,item in bib_df.iterrows():
        for cit in item['scholar citations']:
            if any(bib_df['scholar paper id'].isin([cit['paperId']])):
                bib_df.at[index, 'scholar citation count not-NIME'] = bib_df.at[index, 'scholar citation count not-NIME'] + 1

    bib_df.to_pickle('./cache/df/cleaned_bib_df.obj')  

    return bib_df

def generate_cit_ref_auth_df(bib_df):

    if os.path.isfile('./cache/df/cit_df.obj') and os.path.isfile('./cache/df/ref_df.obj') and os.path.isfile('./cache/df/auth_df.obj'):
        cit_df = pd.read_pickle('./cache/df/cit_df.obj')
        ref_df = pd.read_pickle('./cache/df/ref_df.obj')
        auth_df = pd.read_pickle('./cache/df/auth_df.obj')
        return cit_df, ref_df, auth_df

    years = np.sort(bib_df['year'].unique())
    years_empty_dict = dict.fromkeys(years,0)

    NIME_authors_id = bib_df['scholar authors id'].tolist()
    NIME_authors_id = list(chain.from_iterable(NIME_authors_id))
    NIME_authors_id = list(dict.fromkeys(NIME_authors_id))
    NIME_authors_id.remove('N/A')

    cit_df = pd.DataFrame(columns=['paperId', 'title', 'year', 's2FieldsOfStudy', 'publicationTypes', 'journal', 'venue', 'authors', 'count', 'count_year', 'in NIME'])
    ref_df = pd.DataFrame(columns=['paperId', 'title', 'year', 's2FieldsOfStudy', 'publicationTypes', 'journal', 'venue', 'authors', 'count', 'count x cit', 'count_year', 'in NIME'])
    auth_df = pd.DataFrame(columns=['authorId', 'name', 'cit_count', 'cit_count_year', 'ref_count', 'ref_count_year', 'in NIME'])

    for index,item in bib_df.iterrows():
        for cit in item['scholar citations']:
            for auth in cit['authors']:
                if auth['authorId'] is not None:
                    if any(auth_df['authorId'].isin([auth['authorId']])):
                        idx = auth_df[auth_df['authorId'] == auth['authorId']].index.to_list()[0]
                        auth_df.at[idx, 'cit_count'] = auth_df.at[idx, 'cit_count'] + 1
                        auth_df.at[idx, 'cit_count_year'][item['year']] = auth_df.at[idx, 'cit_count_year'][item['year']] + 1
                    else:
                        temp = auth.copy()
                        temp['cit_count'] = 1
                        temp['cit_count_year'] = years_empty_dict.copy()
                        temp['cit_count_year'][item['year']] = temp['cit_count_year'][item['year']] + 1
                        temp['ref_count'] = 0
                        temp['ref_count_year'] = years_empty_dict.copy()
                        temp['in NIME'] = False
                        if temp['authorId'] in NIME_authors_id:
                            temp['in NIME'] = True
                        auth_df = auth_df.append(temp, ignore_index=True)
            if cit['paperId'] is None:
                continue
            if any(cit_df['paperId'].isin([cit['paperId']])):
                idx = cit_df[cit_df['paperId'] == cit['paperId']].index.to_list()[0]
                cit_df.at[idx, 'count'] = cit_df.at[idx, 'count'] + 1
                cit_df.at[idx, 'count_year'][item['year']] = cit_df.at[idx, 'count_year'][item['year']] + 1
            else:
                temp = cit.copy()
                temp['count'] = 1
                temp['count_year'] = years_empty_dict.copy()
                temp['count_year'][item['year']] = temp['count_year'][item['year']] + 1
                temp['in NIME'] = any(bib_df['scholar paper id'].isin([cit['paperId']]))
                cit_df = cit_df.append(temp, ignore_index=True)
              
        for ref in item['scholar references']:
            for auth in ref['authors']:
                if auth['authorId'] is not None:
                    if any(auth_df['authorId'].isin([auth['authorId']])):
                        idx = auth_df[auth_df['authorId'] == auth['authorId']].index.to_list()[0]
                        auth_df.at[idx, 'ref_count'] = auth_df.at[idx, 'ref_count'] + 1
                        auth_df.at[idx, 'ref_count_year'][item['year']] = auth_df.at[idx, 'ref_count_year'][item['year']] + 1
                    else:
                        temp = auth.copy()
                        temp['cit_count'] = 0
                        temp['cit_count_year'] = years_empty_dict.copy()
                        temp['ref_count'] = 1
                        temp['ref_count_year'] = years_empty_dict.copy()
                        temp['ref_count_year'][item['year']] = temp['ref_count_year'][item['year']] + 1
                        temp['in NIME'] = False
                        if temp['authorId'] in NIME_authors_id:
                            temp['in NIME'] = True
                        auth_df = auth_df.append(temp, ignore_index=True)
            if ref['paperId'] is None:
                continue
            if any(ref_df['paperId'].isin([ref['paperId']])):
                idx = ref_df[ref_df['paperId'] == ref['paperId']].index.to_list()[0]
                ref_df.at[idx, 'count'] = ref_df.at[idx, 'count'] + 1
                ref_df.at[idx, 'count x cit'] = ref_df.at[idx, 'count x cit'] + item['scholar citation count']
                ref_df.at[idx, 'count_year'][item['year']] = ref_df.at[idx, 'count_year'][item['year']] + 1
            else:
                temp = ref.copy()
                temp['count'] = 1
                temp['count x cit'] = item['scholar citation count']
                temp['count_year'] = years_empty_dict.copy()
                temp['count_year'][item['year']] = temp['count_year'][item['year']] + 1
                temp['in NIME'] = any(bib_df['scholar paper id'].isin([ref['paperId']]))
                ref_df = ref_df.append(temp, ignore_index=True)

    cit_df.to_pickle('./cache/df/cit_df.obj')
    ref_df.to_pickle('./cache/df/ref_df.obj')
    auth_df.to_pickle('./cache/df/auth_df.obj')

    return cit_df, ref_df, auth_df

def load_conf_csv(filepath):

    try: # accommodate regional delimiters
        conf_df = pd.read_csv(filepath)
    except:
        conf_df = pd.read_csv(filepath, sep=';')

    return conf_df

def gen_wordcloud(processed_data):
    from wordcloud import WordCloud

    for data in processed_data:
        words = [word for doc in data[1] for word in doc]
        counter = dict(collections.Counter(words))
        wc = WordCloud(width=1920, height=1444,
                        background_color="white", max_words=500
                        ).generate_from_frequencies(counter)
        plt.imshow(wc, interpolation='bilinear')
        plt.axis("off")
        plt.savefig(f'./output/wordcloud_{data[0]}.png', dpi=300)
    pa_print.nprint('\nGenerated .png files in ./output!')

def stats_bibliometric(bib_df, cit_df, ref_df, auth_df):

    pa_print.nprint('\nComputing bibliometric statistics...')

    years = np.sort(bib_df['year'].unique())
    years_rel = np.delete(years, np.where((years == 2021) | (years == 2022))) #removing PubPub years

    outtxt = ''

    # papers total and per year, number of references, number of citations
    papers_total = len(bib_df.index)
    papers_per_year = bib_df['year'].value_counts(sort=False)
    papers_total_in_scholar = len(bib_df.loc[is_not_nan(bib_df['scholar paper id'])])
    papers_total_in_scholar_reliable = len(bib_df.loc[bib_df['scholar valid'] ==  True]) 
    outtxt += '\nTotal papers %d' % papers_total
    outtxt += '\nTotal papers found in scholar %d equivalent to %f %%' % (papers_total_in_scholar, 100*papers_total_in_scholar/papers_total)
    outtxt += '\nTotal papers with reliable data in scholar %d equivalent to %f %%' % (papers_total_in_scholar_reliable, 100*papers_total_in_scholar_reliable/papers_total)
   
    #total authors
    total_authors = bib_df['author count'].sum()

    nime_auth_df = pd.DataFrame(index=range(bib_df['author count'].sum()), columns=['year','name','gender1','gender2','citations','first','mixed'])
    cnt = 0
    for idx, item in bib_df.iterrows():
        author_count = item['author count']
        for i in range(author_count):
            nime_auth_df.loc[cnt,'name'] = item['author names'][i][0] + ' ' + item['author names'][i][1]
            cnt = cnt + 1
    temp = nime_auth_df.drop_duplicates(subset = ['name'])
    unique_authors = len(temp.index)

    NIME_authors_id = bib_df['scholar authors id'].tolist()
    NIME_authors_id = list(chain.from_iterable(NIME_authors_id))
    NIME_authors_id = list(dict.fromkeys(NIME_authors_id))
    NIME_authors_id.remove('N/A')


    outtxt += '\nTotal authors %d' % total_authors
    outtxt += '\nTotal unique authors %d' % unique_authors
    outtxt += '\nTotal authors found in scholar %d' % len(NIME_authors_id)

    # total and average average number of citations and references
    citations_total_arr = []
    references_total_arr = []

    for index,item in bib_df.iterrows():
        citations_total_arr = np.append(citations_total_arr, len(item['scholar citations']))
        if item['scholar valid']:
            references_total_arr = np.append(references_total_arr, len(item['scholar references']))

    outtxt += '\nTotal references %d' % references_total_arr.sum()
    outtxt += '\nTotal citations %d' % citations_total_arr.sum()
    outtxt += '\nReferences per paper average %f, standard deviation %f' % (references_total_arr.mean(), references_total_arr.std())
    outtxt += '\nCitations per paper average %f, standard deviation %f' % (citations_total_arr.mean(), citations_total_arr.std())
    outtxt += '\nUnique papers in references %d out of which %d in NIME proceedings' % (len(ref_df.index), len(ref_df[ref_df['in NIME'] == True]))
    outtxt += '\nUnique citing papers %d out of which %d in NIME proceedings' % (len(cit_df.index), len(ref_df[ref_df['in NIME'] == True]))
    outtxt += '\nUnique reference authors %d out of which %d published in NIME' % (len(auth_df[auth_df['ref_count'] > 0]), len(auth_df[(auth_df['ref_count'] > 0) & auth_df['in NIME'] == True]))
    outtxt += '\nUnique citation authors %d out of which %d published in NIME' % (len(auth_df[auth_df['cit_count'] > 0]), len(auth_df[(auth_df['cit_count'] > 0) & auth_df['in NIME'] == True]))
    

    papers_per_year = pd.DataFrame(index = years)
    citations_per_year = pd.DataFrame(index = years)
    references_per_year = pd.DataFrame(index = years)

    papers_per_year['total'] = ''
    papers_per_year['total in scholar'] = ''
    papers_per_year['total reliable in scholar'] = ''
    citations_per_year['total'] = ''
    citations_per_year['norm by numpaper'] = ''
    citations_per_year['norm by agepaper'] = ''
    citations_per_year['norm by num_and_agepaper'] = ''
    references_per_year['total'] = ''
    references_per_year['new'] = ''
    references_per_year['norm by numpaper'] = ''

    ref_df['found'] = False

    for y in years:
        papers = bib_df.loc[bib_df['year'] == y]
        papers_per_year.at[y, 'total'] = len(papers.index)
        papers_per_year.at[y, 'total in scholar'] = len(papers.loc[is_not_nan(papers['scholar paper id'])])
        papers_per_year.at[y, 'total reliable in scholar'] = len(papers.loc[papers['scholar valid'] ==  True])
        acc_citations = 0
        acc_references = 0
        acc_new_ref = 0
        for index,item in papers.iterrows():
            acc_citations = acc_citations + len(item['scholar citations'])
            if item['scholar valid']:
                acc_references = acc_references + len(item['scholar references'])
                for ref in item['scholar references']:
                    if any(ref_df['paperId'].isin([ref['paperId']])):
                        temp = ref_df.index[ref_df['paperId'] == ref['paperId']].tolist()[0]
                        if ref_df.at[temp, 'found'] == False:
                            ref_df.at[temp, 'found'] = True
                            acc_new_ref = acc_new_ref + 1
        citations_per_year.at[y,'total'] = acc_citations
        citations_per_year.at[y,'norm by numpaper'] = acc_citations/len(papers)
        citations_per_year.at[y,'norm by agepaper'] = acc_citations/papers['age'].values[0]
        citations_per_year.at[y,'norm by num_and_agepaper'] = (acc_citations/len(papers))/papers['age'].values[0]
        papers_in_scholar = papers.loc[is_not_nan(papers['scholar paper id'])]
        references_per_year.at[y,'total'] = acc_references
        references_per_year.at[y,'new'] = acc_new_ref
        references_per_year.at[y,'norm by numpaper'] = acc_references/len(papers_in_scholar)
    
    temp = bib_df[bib_df['scholar valid'] == True]
    papers_by_references = temp['scholar reference count'].value_counts(sort=False).sort_index()
    papers_by_citations = bib_df['scholar citation count'].value_counts(sort=False).sort_index()

    ref_df = ref_df.drop(columns=['found'])

    # number of citations and references from/to NIME paper and authors
    bib_df['citations from NIME'] = ''
    bib_df['references to NIME'] = ''
    bib_df['citations from NIME authors'] = ''
    bib_df['references to NIME authors'] = ''

    references_age_distr_relative = {}
    references_age_distr_relative_year = {}
    citations_age_distr_relative = {}
    citations_age_distr_relative_year = {}

    for y in years:
        papers = bib_df.loc[bib_df['year'] == y]
        references_age_distr_relative_year[y] = {}
        citations_age_distr_relative_year[y] = {}
        for index,item in papers.iterrows():
            cit_acc = 0
            ref_acc = 0
            bib_df.at[index, 'citations from NIME authors'] = 0
            bib_df.at[index, 'references to NIME authors'] = 0
            for cit in item['scholar citations']:
                if cit['year']:
                    diff = cit['year'] - item['year']
                    if diff in citations_age_distr_relative:
                        citations_age_distr_relative[diff] = citations_age_distr_relative[diff] + 1
                    else:
                        citations_age_distr_relative[diff] = 1
                    if diff in citations_age_distr_relative_year[y]:
                        citations_age_distr_relative_year[y][diff] = citations_age_distr_relative_year[y][diff] + 1
                    else:
                        citations_age_distr_relative_year[y][diff] = 1
                if any(bib_df['scholar paper id'].isin([cit['paperId']])):
                    cit_acc = cit_acc + 1
                for auth in cit['authors']:
                    if auth['authorId'] in NIME_authors_id:
                        bib_df.at[index, 'citations from NIME authors'] = bib_df.at[index, 'citations from NIME authors'] + 1
                        break
            bib_df.at[index,'citations from NIME'] = cit_acc
            if item['scholar valid']:
                for ref in item['scholar references']:
                    if ref['year']:
                        diff = item['year'] - ref['year'] 
                        if diff in references_age_distr_relative:
                            references_age_distr_relative[diff] = references_age_distr_relative[diff] + 1
                        else:
                            references_age_distr_relative[diff] = 1
                        if diff in references_age_distr_relative_year[y]:
                            references_age_distr_relative_year[y][diff] = references_age_distr_relative_year[y][diff] + 1
                        else:
                            references_age_distr_relative_year[y][diff] = 1
                    if any(bib_df['scholar paper id'].isin([ref['paperId']])):
                        ref_acc = ref_acc + 1
                    for auth in ref['authors']:
                        if auth['authorId'] in NIME_authors_id:
                            bib_df.at[index, 'references to NIME authors'] = bib_df.at[index, 'references to NIME authors'] + 1
                            break
                bib_df.at[index,'references to NIME'] = ref_acc
            else:
                bib_df.at[index,'references to NIME'] = 0


    references_age_distr_relative = pd.DataFrame.from_dict(references_age_distr_relative, orient='index').sort_index()
    citations_age_distr_relative = pd.DataFrame.from_dict(citations_age_distr_relative, orient='index').sort_index()
    references_age_distr_relative_year = pd.DataFrame.from_dict(references_age_distr_relative_year, orient='index')
    citations_age_distr_relative_year = pd.DataFrame.from_dict(citations_age_distr_relative_year, orient='index')

    outtxt += '\nTotal references to NIME %d equivalent to %f %%' % (bib_df['references to NIME'].sum(), 100*bib_df['references to NIME'].sum()/references_total_arr.sum())
    outtxt += '\nTotal citations from NIME %d equivalent to %f %%' % (bib_df['citations from NIME'].sum(), 100*bib_df['citations from NIME'].sum()/citations_total_arr.sum())

    citations_per_year['from NIME'] = ''
    citations_per_year['from NIME percentage'] = ''
    references_per_year['to NIME'] = ''
    references_per_year['to NIME percentage'] = ''

    for y in years:
        papers = bib_df.loc[bib_df['year'] == y]
        citations_per_year.at[y, 'from NIME'] = papers['citations from NIME'].sum()
        citations_per_year.at[y, 'from NIME percentage'] = 100*citations_per_year.at[y, 'from NIME']/citations_per_year.at[y, 'total']
        references_per_year.at[y, 'to NIME'] = papers['references to NIME'].sum()
        references_per_year.at[y, 'to NIME percentage'] = 100*references_per_year.at[y, 'to NIME']/references_per_year.at[y, 'total']

    outtxt += '\nTotal references to NIME authors %d equivalent to %f %%' % (bib_df['references to NIME authors'].sum(), 100*bib_df['references to NIME authors'].sum()/references_total_arr.sum())
    outtxt += '\nTotal citations from authors NIME %d equivalent to %f %%' % (bib_df['citations from NIME authors'].sum(), 100*bib_df['citations from NIME authors'].sum()/citations_total_arr.sum())

    citations_per_year['from NIME authors'] = ''
    citations_per_year['from NIME authors percentage'] = ''
    references_per_year['to NIME authors'] = ''
    references_per_year['to NIME authors percentage'] = ''

    for y in years:
        papers = bib_df.loc[bib_df['year'] == y]
        citations_per_year.at[y, 'from NIME authors'] = papers['citations from NIME authors'].sum()
        citations_per_year.at[y, 'from NIME authors percentage'] = 100*citations_per_year.at[y, 'from NIME authors']/citations_per_year.at[y, 'total']
        references_per_year.at[y, 'to NIME authors'] = papers['references to NIME authors'].sum()
        references_per_year.at[y, 'to NIME authors percentage'] = 100*references_per_year.at[y, 'to NIME authors']/references_per_year.at[y, 'total']


    ref_fields = {}
    ref_fields_nime = {}
    cit_fields = {}
    cit_fields_nime = {}
    proc_fields = {}
    ref_venues = {}
    cit_venues = {}
    ref_fields_per_year = {}
    ref_fields_per_year_nime = {}
    cit_fields_per_year = {}
    cit_fields_per_year_nime = {}
    proc_fields_per_year = {}
    ref_venues_per_year = {}
    cit_venues_per_year = {}
    pub_venues = {}

    for y in years:
        papers = bib_df.loc[bib_df['year'] == y]
        cit_fields_per_year[y] = {}
        ref_fields_per_year[y] = {}
        cit_fields_per_year_nime[y] = {}
        ref_fields_per_year_nime[y] = {}
        proc_fields_per_year[y] = {}
        ref_venues_per_year[y] = {}
        cit_venues_per_year[y] = {}
        for index,item in papers.iterrows():
            for fld in item['scholar field of study']:
                if fld['category'] in proc_fields:
                    proc_fields[fld['category']] = proc_fields[fld['category']] + 1
                else:
                    proc_fields[fld['category']] = 1
                if fld['category'] in proc_fields_per_year[y]:
                    proc_fields_per_year[y][fld['category']] = proc_fields_per_year[y][fld['category']] + 1
                else:
                    proc_fields_per_year[y][fld['category']] = 1
            for cit in item['scholar citations']:
                if cit['publicationVenue']:
                    if 'id' in cit['publicationVenue']:
                        if cit['publicationVenue']['id'] in cit_venues:
                            cit_venues[cit['publicationVenue']['id']] = cit_venues[cit['publicationVenue']['id']] + 1
                        else:
                            cit_venues[cit['publicationVenue']['id']] = + 1
                        if cit['publicationVenue']['id'] in cit_venues_per_year[y]:
                            cit_venues_per_year[y][cit['publicationVenue']['id']] = cit_venues_per_year[y][cit['publicationVenue']['id']] + 1
                        else:
                            cit_venues_per_year[y][cit['publicationVenue']['id']] = + 1
                        if cit['publicationVenue']['id'] not in pub_venues:
                            if 'alternate_names' in cit['publicationVenue']:
                                pub_venues[cit['publicationVenue']['id']] = cit['publicationVenue']['alternate_names']
                            else:
                                pub_venues[cit['publicationVenue']['id']] = cit['publicationVenue']['name']
                if cit['s2FieldsOfStudy']:
                    for fld in cit['s2FieldsOfStudy']:
                        if fld['category'] in cit_fields:
                            cit_fields[fld['category']] = cit_fields[fld['category']] + 1
                        else:
                            cit_fields[fld['category']] = 1
                        if fld['category'] in cit_fields_per_year[y]:
                            cit_fields_per_year[y][fld['category']] = cit_fields_per_year[y][fld['category']] + 1
                        else:
                            cit_fields_per_year[y][fld['category']] = 1
                    if any(bib_df['scholar paper id'].isin([cit['paperId']])):
                        for fld in cit['s2FieldsOfStudy']:
                            if fld['category'] in cit_fields_nime:
                                cit_fields_nime[fld['category']] = cit_fields_nime[fld['category']] + 1
                            else:
                                cit_fields_nime[fld['category']] = 1
                            if fld['category'] in cit_fields_per_year_nime[y]:
                                cit_fields_per_year_nime[y][fld['category']] = cit_fields_per_year_nime[y][fld['category']] + 1
                            else:
                                cit_fields_per_year_nime[y][fld['category']] = 1
            if item['scholar valid']:
                for ref in item['scholar references']:
                    if ref['publicationVenue']:
                        if 'id' in ref['publicationVenue']:
                            if ref['publicationVenue']['id'] in ref_venues:
                                ref_venues[ref['publicationVenue']['id']] = ref_venues[ref['publicationVenue']['id']] + 1
                            else:
                                ref_venues[ref['publicationVenue']['id']] = + 1
                            if ref['publicationVenue']['id'] in ref_venues_per_year[y]:
                                ref_venues_per_year[y][ref['publicationVenue']['id']] = ref_venues_per_year[y][ref['publicationVenue']['id']] + 1
                            else:
                                ref_venues_per_year[y][ref['publicationVenue']['id']] = + 1
                            if ref['publicationVenue']['id'] not in pub_venues:
                                if 'alternate_names' in ref['publicationVenue']:
                                    pub_venues[ref['publicationVenue']['id']] = ref['publicationVenue']['alternate_names']
                                else:
                                    pub_venues[ref['publicationVenue']['id']] = ref['publicationVenue']['name']
                    if ref['s2FieldsOfStudy']:
                        for fld in ref['s2FieldsOfStudy']:
                            if fld['category'] in ref_fields:
                                ref_fields[fld['category']] = ref_fields[fld['category']] + 1
                            else:
                                ref_fields[fld['category']] = 1
                            if fld['category'] in ref_fields_per_year[y]:
                                ref_fields_per_year[y][fld['category']] = ref_fields_per_year[y][fld['category']] + 1
                            else:
                                ref_fields_per_year[y][fld['category']] = 1
                    if any(bib_df['scholar paper id'].isin([ref['paperId']])):
                        for fld in ref['s2FieldsOfStudy']:
                            if fld['category'] in ref_fields_nime:
                                ref_fields_nime[fld['category']] = ref_fields_nime[fld['category']] + 1
                            else:
                                ref_fields_nime[fld['category']] = 1
                            if fld['category'] in ref_fields_per_year_nime[y]:
                                ref_fields_per_year_nime[y][fld['category']] = ref_fields_per_year_nime[y][fld['category']] + 1
                            else:
                                ref_fields_per_year_nime[y][fld['category']] = 1  

    ref_fields = pd.DataFrame.from_dict(ref_fields, orient='index')
    cit_fields = pd.DataFrame.from_dict(cit_fields, orient='index')
    ref_fields_nime = pd.DataFrame.from_dict(ref_fields_nime, orient='index')
    cit_fields_nime = pd.DataFrame.from_dict(cit_fields_nime, orient='index')
    ref_fields_per_year = pd.DataFrame.from_dict(ref_fields_per_year, orient='index')
    cit_fields_per_year = pd.DataFrame.from_dict(cit_fields_per_year, orient='index')
    ref_fields_per_year_nime = pd.DataFrame.from_dict(ref_fields_per_year_nime, orient='index')
    cit_fields_per_year_nime = pd.DataFrame.from_dict(cit_fields_per_year_nime, orient='index')
    ref_venues = pd.DataFrame.from_dict(ref_venues, orient='index')
    cit_venues = pd.DataFrame.from_dict(cit_venues, orient='index')
    ref_venues_per_year = pd.DataFrame.from_dict(ref_venues_per_year, orient='index')
    cit_venues_per_year = pd.DataFrame.from_dict(cit_venues_per_year, orient='index')
    proc_fields = pd.DataFrame.from_dict(proc_fields, orient='index')
    proc_fields_per_year = pd.DataFrame.from_dict(proc_fields_per_year, orient='index')


    for index,item in ref_venues.iterrows():
        ref_venues.at[index, 'name'] = pub_venues[index]

    for index,item in cit_venues.iterrows():
        cit_venues.at[index, 'name'] = pub_venues[index]
    
    temp = []
    for id in list(ref_venues_per_year.columns):
        temp.append(' '.join(pub_venues[id]))
    ref_venues_per_year.columns = temp

    temp = []
    for id in list(cit_venues_per_year.columns):
        temp.append(' '.join(pub_venues[id]))
    cit_venues_per_year.columns = temp
    

    outtxt += '\nReferences number of publication venues %d' % (len(ref_venues))
    outtxt += '\nCitations number of publication venues %d' % (len(cit_venues))

    # papers both citing and referencing
    ref_cit_df = pd.DataFrame(columns=list(ref_df.columns.values))
    ref_cit_df['cit count'] = ''
    ref_cit_df['ref+cit count'] = ''

    idx = 0
    for ref_idx,ref in ref_df.iterrows():
        if any(cit_df['paperId'].isin([ref['paperId']])):
            cit_idx = np.where(cit_df['paperId'] == ref['paperId'])
            cit_idx = cit_idx[0][0]
            ref_cit_df = ref_cit_df.append(ref, ignore_index=True)
            ref_cit_df.at[idx, 'cit count'] = cit_df.at[cit_idx, 'count']
            ref_cit_df.at[idx, 'ref+cit count'] = ref_cit_df.at[idx, 'count'] + ref_cit_df.at[idx, 'cit count']
            idx = idx + 1
    
    ref_cit_df = ref_cit_df.rename(columns = {'count':'ref count'})
    ref_cit_df = ref_cit_df.drop(columns=['count x cit', 'count_year'])

    outtxt += '\nNumber of papers in both references and citations %d out of which %d in NIME' % (len(ref_cit_df.index), len(ref_cit_df[ref_cit_df['in NIME'] ==  True]))
    outtxt += '\nCitations number of publication venues %d' % (len(cit_venues))

    # wordclouds title ref, title cit, tldr
    processed_tldr = []
    processed_cit_titles = []
    processed_cit_titles_count = []
    processed_ref_titles = []
    processed_ref_titles_count = []

    for index,item in bib_df.iterrows():
        if item['scholar tldr']:
            tldr = clean_text(item['scholar tldr']['text'], user_config)
            processed_tldr.append(tldr)

    for index,item in cit_df.iterrows():
        if item['title']:
            tit = clean_text(item['title'], user_config)
            processed_cit_titles.append(tit)
            processed_cit_titles_count.append(tit*item['count'])

    for index,item in ref_df.iterrows():
        if item['title']:
            tit = clean_text(item['title'], user_config)
            processed_ref_titles.append(tit)
            processed_ref_titles_count.append(tit*item['count'])

    processed_data = [('tldr', processed_tldr), ('cit_titles', processed_cit_titles), ('cit_titles_count', processed_cit_titles_count), ('ref_titles', processed_ref_titles), ('ref_titles_count', processed_ref_titles_count)]

    gen_wordcloud(processed_data)


    # scatter plot of dimensionality reduced embedding with citation count
    embedding_list = []
    embedding_year_list = []
    embedding_cit_count_list = []
    embedding_inf_cit_count_list = []

    for index,item in bib_df.iterrows():
        if item['year'] not in years_rel:
            continue
        if 'vector' in item['scholar embedding']:
            embedding_list.append(item['scholar embedding']['vector'])
            embedding_year_list.append(item['year'])
            embedding_cit_count_list.append(item['scholar citation count'])
            embedding_inf_cit_count_list.append(item['scholar influential citation count'])

    embedding_array = np.array(embedding_list) 
    embedding_year_array = np.array(embedding_year_list) 
    embedding_cit_count_array = np.array(embedding_cit_count_list)
    embedding_inf_cit_count_array = np.array(embedding_inf_cit_count_list)   

    embedding_dr = TSNE(n_components=2, learning_rate='auto',init='random', perplexity=25).fit_transform(embedding_array)
    colors = cm.nipy_spectral(np.linspace(0.03, 0.97, len(years_rel)))
    
    figure = plt.figure()
    figure.set_size_inches(8, 8)
    for y, c in zip(years_rel, colors):
        indexes = np.where(embedding_year_array == y)
        plt.scatter(embedding_dr[indexes,0],embedding_dr[indexes,1],label=y, color=c, s=embedding_cit_count_array[indexes]+2)
    plt.axis('off')
    plt.savefig('./output/reduced_embedding_scatter_cit.png', dpi=150)
    figure.set_size_inches(8, 16)
    plt.legend(loc='best', frameon=False)
    plt.savefig('./output/reduced_embedding_scatter_cit_leg.png', dpi=150)


    with open('./output/bibliometric.txt', 'w') as text_file:
        text_file.write(outtxt)

    with pd.ExcelWriter('./output/bibliometric.xlsx') as writer:
        bib_df.to_excel(writer, sheet_name='NIME Papers', header=True)
        ref_df.to_excel(writer, sheet_name='References', header=True)
        cit_df.to_excel(writer, sheet_name='Citations', header=True)
        ref_cit_df.to_excel(writer, sheet_name='References and Citations', header=True)
        auth_df.to_excel(writer, sheet_name='Ref and Cit Authors', header=True)
        papers_per_year.to_excel(writer, sheet_name='Papers per year', header=True)
        references_per_year.to_excel(writer, sheet_name='References per year', header=True)
        citations_per_year.to_excel(writer, sheet_name='Citations per year', header=True)
        papers_by_references.to_excel(writer, sheet_name='Papers by references', header=False)
        papers_by_citations.to_excel(writer, sheet_name='Papers by citations', header=False)
        references_age_distr_relative.to_excel(writer, sheet_name='Reference rel. age dist', header=False)
        citations_age_distr_relative.to_excel(writer, sheet_name='Citation rel. age dist', header=False)
        references_age_distr_relative_year.to_excel(writer, sheet_name='Reference rel. age by year dist', header=True)
        citations_age_distr_relative_year.to_excel(writer, sheet_name='Citation rel. age by year dist', header=True)
        ref_fields.to_excel(writer, sheet_name='Reference fields distr', header=False)
        cit_fields.to_excel(writer, sheet_name='Citation fields distr', header=False)
        ref_fields_per_year.to_excel(writer, sheet_name='Reference fields distr per year', header=True)
        cit_fields_per_year.to_excel(writer, sheet_name='Citation fields distr per year', header=True)
        ref_fields_nime.to_excel(writer, sheet_name='Reference NIME fields distr', header=False)
        cit_fields_nime.to_excel(writer, sheet_name='Citation NIME fields distr', header=False)
        ref_fields_per_year_nime.to_excel(writer, sheet_name='Ref NIME fields distr per year', header=True)
        cit_fields_per_year_nime.to_excel(writer, sheet_name='Cit NIME fields distr per year', header=True)
        proc_fields.to_excel(writer, sheet_name='Proc fields distr', header=False)
        proc_fields_per_year.to_excel(writer, sheet_name='Proc fields distr per year', header=True)
        ref_venues.to_excel(writer, sheet_name='Reference pub venues', header=False)
        cit_venues.to_excel(writer, sheet_name='Citation pub venues', header=False)
        ref_venues_per_year.to_excel(writer, sheet_name='Reference pub venues per year', header=True)
        cit_venues_per_year.to_excel(writer, sheet_name='Citation pub venue per year', header=True)


    pa_print.nprint('\nGenerated bibliometric.txt and bibliometric.xlsx in ./output!')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze the metadata stored in the output/export.csv')
    parser.add_argument('-n', '--nime', action='store_true', default=False,
                        help='uses NIME based corrections')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help='prints out analysis stages results')
    args = parser.parse_args()

    # Sets global print command
    pa_print.init(args)

    # Print notice
    pa_print.lprint()

    os.makedirs('./output', exist_ok=True)

    # Load databases
    user_config = import_config('./resources/custom.csv')
    conf_df = load_conf_csv('./resources/conferences.csv')
    bib_df = load_bib_csv('./output/export.csv',user_config[3])
    cit_df, ref_df, auth_df = generate_cit_ref_auth_df(bib_df)

    answer = boolify(input("\nGenerate bibliometric statistics? (y/N): "))
    if answer:
        stats_papers_out = stats_bibliometric(bib_df, cit_df, ref_df, auth_df)