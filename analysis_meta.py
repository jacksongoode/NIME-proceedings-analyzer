# This file is part of the NIME Proceedings Analyzer (NIME PA)
# Copyright (C) 2022 Jackson Goode, Stefano Fasciani

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
if sys.version_info < (3, 7):
    print("Please upgrade Python to version 3.7.0 or higher")
    sys.exit()
import os
from os import path
import argparse
import ast
from collections import Counter
from itertools import cycle

# External
import gensim
import unidecode
import re
import pandas as pd
from pandas import DataFrame
import numpy as np
import datetime
from scipy.optimize import curve_fit

# Helper
import pa_print
from pa_utils import try_index, import_config, boolify

def lotka_law(x, n, c):
    return c / np.power(x, n)

def is_not_nan(num):
    return num == num

def load_bib_csv(filepath, selectedyears):
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

    return bib_df

def load_conf_csv(filepath):

    try: # accommodate regional delimiters
        conf_df = pd.read_csv(filepath)
    except:
        conf_df = pd.read_csv(filepath, sep=';')

    return conf_df

def papers_perc_citations(bib_df, perc):
    papers_total = len(bib_df.index)
    cit_total = bib_df['scholar citation count'].sum()
    temp = bib_df['scholar citation count'].sort_values(ascending=False)
    i = 0
    while True:
        current_perc = temp[0:i].sum() / cit_total
        if current_perc > perc:
            break
        i = i + 1

    return i, i/papers_total

def papers_perc_citations_year(bib_df, perc):
    years = bib_df['year'].unique()
    out = pd.DataFrame(index = years)
    out['number of papers'] = ''
    out['percentage papers'] = ''
    for y in years:
        temp1 = bib_df.loc[bib_df['year'] == y]
        papers_total = len(temp1.index)
        cit_total = temp1['scholar citation count'].sum()
        temp2 = temp1['scholar citation count'].sort_values(ascending=False)
        i = 0
        while True:
            current_perc = temp2[0:i].sum() / cit_total
            if current_perc > perc:
                out.at[y,'number of papers'] = i
                out.at[y,'percentage papers'] = 100*i/papers_total
                break
            i = i + 1

    return out

def papers_top_citations_year(bib_df):
    years = bib_df['year'].unique()
    out = pd.DataFrame(index = years)
    out['title'] = ''
    out['scholar citation count'] = ''
    out['NIME reader'] = ''
    for y in years:
        temp = bib_df.loc[bib_df['year'] == y]
        max_cit = temp['scholar citation count'].max()
        out.at[y,'title'] = temp.loc[bib_df['scholar citation count'] == max_cit]['title'].to_string(index=False)
        out.at[y,'scholar citation count'] = temp.loc[bib_df['scholar citation count'] == max_cit]['scholar citation count'].to_string(index=False)
        out.at[y,'NIME reader'] = temp.loc[bib_df['scholar citation count'] == max_cit]['NIME reader'].to_string(index=False)

    return out

# Functions for generating stat-specific metrics
def stats_papers(bib_df):

    pa_print.nprint('\nComputing papers statistics...')

    outtxt = ''
    # papers in total and per year
    papers_total = len(bib_df.index)
    papers_per_year = bib_df['year'].value_counts(sort=False)
    outtxt += '\nTotal papers %d' % papers_total

    # growth of NIME papers corpus per year
    papers_per_year_cumulative = bib_df['year'].value_counts(sort=False).cumsum()

    # full-short-other papers
    pre21_bib_df = bib_df.loc[(bib_df['year'] <= 2020)]
    post21_bib_df = bib_df.loc[(bib_df['year'] >= 2021)]

    temp = pre21_bib_df.loc[(pre21_bib_df['page count'] > 4)]
    full_papers_per_year_pre21 = temp['year'].value_counts(sort=False)
    temp = post21_bib_df.loc[(post21_bib_df['word count'] > 3000)]
    full_papers_per_year_post21 = temp['year'].value_counts(sort=False)
    full_papers_per_year = pd.concat([full_papers_per_year_pre21,full_papers_per_year_post21], axis=0)
    full_papers_total = full_papers_per_year.sum()

    temp = pre21_bib_df.loc[(pre21_bib_df['page count'] > 2) & (pre21_bib_df['page count'] <= 4)]
    short_papers_per_year_pre21 = temp['year'].value_counts(sort=False)
    temp = post21_bib_df.loc[(post21_bib_df['word count'] > 1500) & (post21_bib_df['word count'] <= 3000)]
    short_papers_per_year_post21 = temp['year'].value_counts(sort=False)
    short_papers_per_year = pd.concat([short_papers_per_year_pre21,short_papers_per_year_post21], axis=0)
    short_papers_total = short_papers_per_year.sum()

    temp = pre21_bib_df.loc[(pre21_bib_df['page count'] <= 2)]
    other_papers_per_year_pre21 = temp['year'].value_counts(sort=False)
    temp = post21_bib_df.loc[(post21_bib_df['word count'] <= 1500)]
    other_papers_per_year_post21 = temp['year'].value_counts(sort=False)
    other_papers_per_year = pd.concat([other_papers_per_year_pre21,other_papers_per_year_post21], axis=0)
    other_papers_total = other_papers_per_year.sum()

    outtxt += '\nTotal Full Papers %d' % full_papers_total
    outtxt += '\nTotal short papers %d' % short_papers_total
    outtxt += '\nTotal Other Papers %d' % other_papers_total

    # pages
    papers_by_pages_pre21 = pre21_bib_df['page count'].value_counts(sort=False)
    average_paper_length_pages_pre21 = pre21_bib_df['page count'].mean()
    max_paper_length_pages_pre21 = pre21_bib_df['page count'].max()
    pages_per_year_average_pre21 = pre21_bib_df.groupby(['year'])['page count'].mean()
    pages_per_year_total_pre21 = pre21_bib_df.groupby(['year'])['page count'].sum()
    longest_papers_pages_pre21 = pre21_bib_df.loc[bib_df['page count'] == max_paper_length_pages_pre21]['title']
    outtxt += '\nAverage papers length pages pre 2021 %f' % average_paper_length_pages_pre21
    outtxt += '\nMax papers length pages pre 2021 %d' % max_paper_length_pages_pre21

    # word count
    words_total = bib_df['word count'].sum()
    words_average = bib_df['word count'].mean()

    pre20 = pre21_bib_df.loc[(pre21_bib_df['page count'] > 4)]
    post21 = post21_bib_df.loc[(post21_bib_df['word count'] > 3000)]
    temp = pd.concat([pre20,post21], axis=0)
    words_average_full = temp['word count'].mean()

    pre20 = pre21_bib_df.loc[(pre21_bib_df['page count'] > 2) & (pre21_bib_df['page count'] <= 4)]
    post21 = post21_bib_df.loc[(post21_bib_df['word count'] > 1500) & (post21_bib_df['word count'] <= 3000)]
    temp = pd.concat([pre20,post21], axis=0)
    words_average_short = temp['word count'].mean()

    pre20 = pre21_bib_df.loc[(pre21_bib_df['page count'] <= 2)]
    post21 = post21_bib_df.loc[(post21_bib_df['word count'] <= 1500)]
    temp = pd.concat([pre20,post21], axis=0)
    words_average_other = temp['word count'].mean()

    temp = pre21_bib_df.loc[pre21_bib_df['page count'] == 6]
    words_average_sixpages_pre20 = temp['word count'].mean()

    temp = pre21_bib_df.loc[pre21_bib_df['page count'] == 4]
    words_average_fourpages_pre20 = temp['word count'].mean()

    temp = pre21_bib_df.loc[pre21_bib_df['page count'] == 2]
    words_average_twopages_pre20 = temp['word count'].mean()

    words_per_year_total = bib_df.groupby(['year'])['word count'].sum()
    words_per_year_average = bib_df.groupby(['year'])['word count'].mean()

    max_paper_words = bib_df['word count'].max()
    longest_papers_words = bib_df.loc[bib_df['word count'] == max_paper_words]['title']

    counts, bins = np.histogram(bib_df['word count'], bins=50)
    center = (bins[:-1] + bins[1:]) / 2
    papers_by_word_count = pd.DataFrame(counts, index = center, columns = ['count'])

    outtxt += '\nTotal word count %d' % words_total
    outtxt += '\nAverage word count %f' % words_average
    outtxt += '\nAverage word count full papers %f' % words_average_full
    outtxt += '\nAverage word count short papers %f' % words_average_short
    outtxt += '\nAverage word count other papers %f' % words_average_other
    outtxt += '\nAverage word count 6 pages pre 2021 %f' % words_average_sixpages_pre20
    outtxt += '\nAverage word count 4 pages pre 2021  %f' % words_average_fourpages_pre20
    outtxt += '\nAverage word count 2 pages pre 2021  %f' % words_average_twopages_pre20
    outtxt += '\nMax papers words %d' % max_paper_words

    # citations
    papers_by_citations = bib_df['scholar citation count'].value_counts(sort=False).sort_index()
    citations_total = bib_df['scholar citation count'].sum()
    citations_per_year = bib_df.groupby(['year'])['scholar citation count'].sum()
    citations_per_year_norm_by_numpaper = bib_df.groupby(['year'])['scholar citation count'].mean()
    citations_per_year_norm_by_agepapers = bib_df.groupby(['year'])['scholar yearly citations'].mean()

    temp = bib_df.loc[bib_df['scholar citation count'] >= 1]
    papers_at_least_1_citation =  len(temp.index)

    temp = bib_df.loc[bib_df['scholar citation count'] >= 10]
    papers_more_10_citations = len(temp.index)

    citations_50perc = papers_perc_citations(bib_df, 0.5)
    citations_90perc = papers_perc_citations(bib_df, 0.9)

    citations_50perc_per_year = papers_perc_citations_year(bib_df, 0.5)
    citations_90perc_per_year = papers_perc_citations_year(bib_df, 0.9)

    temp = bib_df.sort_values(by=['scholar citation count'],ascending=False)
    temp = temp.head(20)
    top_papers_by_citations = temp[['scholar citation count', 'title', 'year', 'NIME reader']]

    temp = bib_df.sort_values(by=['scholar yearly citations'],ascending=False)
    temp = temp.head(20)
    top_papers_by_yearly_citations = temp[['scholar yearly citations', 'title', 'year', 'NIME reader']]

    most_cited_paper_by_pub_year = papers_top_citations_year(bib_df)

    temp = bib_df.loc[bib_df['scholar citation count'].isnull()]
    not_cited_pages = temp['page count'].value_counts(sort=True)

    outtxt += '\nTotal citations %d' % citations_total
    outtxt += '\nPapers with at least 1 citation %d equivaent to %f %%' % (papers_at_least_1_citation,100*papers_at_least_1_citation/papers_total)
    outtxt += '\nPapers with 10 or more citations %d equivalent to %f %%' % (papers_more_10_citations, 100*papers_more_10_citations/papers_total)
    outtxt += '\n50%% citations are from %d papers representing %f %% of the total' % (citations_50perc[0],100*citations_50perc[1])
    outtxt += '\n90%% citations are from %d papers representing %f %% of the total' % (citations_90perc[0],100*citations_90perc[1])

    with pd.ExcelWriter('./output/papers.xlsx') as writer:
        papers_per_year.to_excel(writer, sheet_name='Papers per year', header=False)
        papers_per_year_cumulative.to_excel(writer, sheet_name='Cumulative papers per year', header=False)
        full_papers_per_year.to_excel(writer, sheet_name='Full papers per year', header=False)
        short_papers_per_year.to_excel(writer, sheet_name='Short papers per year', header=False)
        other_papers_per_year.to_excel(writer, sheet_name='Other papers per year', header=False)
        longest_papers_pages_pre21.to_excel(writer, sheet_name='Longest papers in pages pre 21', header=False)
        pages_per_year_total_pre21.to_excel(writer, sheet_name='Pages total per year pre 21', header=False)
        pages_per_year_average_pre21.to_excel(writer, sheet_name='Pages average per year pre 21', header=False)
        papers_by_pages_pre21.to_excel(writer, sheet_name='Papers by page count pre 21', header=False)
        longest_papers_words.to_excel(writer, sheet_name='Longest papers in words', header=False)
        words_per_year_total.to_excel(writer, sheet_name='Words total per year', header=False)
        words_per_year_average.to_excel(writer, sheet_name='Words average per year', header=False)
        papers_by_word_count.to_excel(writer, sheet_name='Papers by word count', header=False)
        citations_per_year.to_excel(writer, sheet_name='Cit. per year', header=False)
        citations_per_year_norm_by_numpaper.to_excel(writer, sheet_name='Cit. pr yr. norm.by #papers', header=False)
        citations_per_year_norm_by_agepapers.to_excel(writer, sheet_name='Cit. pr yr. norm.by #papers&age', header=False)
        citations_50perc_per_year.to_excel(writer, sheet_name='50% cit. from papers per year', header=True)
        citations_90perc_per_year.to_excel(writer, sheet_name='90% cit. from papers per year', header=True)
        top_papers_by_citations.to_excel(writer, sheet_name='Top papers by cit.', header=True)
        top_papers_by_yearly_citations.to_excel(writer, sheet_name='Top papers by yearly cit.', header=True)
        most_cited_paper_by_pub_year.to_excel(writer, sheet_name='Most cited paper by pub. year', header=True)
        papers_by_citations.to_excel(writer, sheet_name='Papers by cit.', header=False)
        not_cited_pages.to_excel(writer, sheet_name='Not cited papers by page length', header=False)

    with open('./output/papers.txt', 'w') as text_file:
        text_file.write(outtxt)

    print('\nGenerated papers.txt and papers.xlsx in ./output!')

def stats_authors(bib_df):

    pa_print.nprint('\nComputing authorship statistics...')

    outtxt = ''

    auth_df = pd.DataFrame(index=range(bib_df['author count'].sum()), columns=['year','name','gender1','gender2','citations','first','mixed'])
    j = 0
    authfem_df = pd.DataFrame(index=bib_df.index, columns=['year','1F'])
    for idx, pub in bib_df.iterrows():
        authfem_df.loc[idx,'year'] = pub['year']
        author_count = pub['author count']
        flag = False
        for i in range(author_count):
            auth_df.loc[j,'year']= pub['year']
            auth_df.loc[j,'name'] = pub['author names'][i][0] + ' ' + pub['author names'][i][1]
            auth_df.loc[j,'gender1'] = pub['author genders'][i]
            auth_df.loc[j,'gender2'] = pub['author genders 2'][i]
            if pub['author genders 2'][i] == 'F':
                flag = True
            auth_df.loc[j,'citations'] = pub['scholar citation count']
            if i == 0:
                auth_df.loc[j,'first'] = True
            else:
                auth_df.loc[j,'first'] = False
            j = j + 1

        authfem_df.loc[idx,'1F'] = flag

    # author count and gender
    total_authors = bib_df['author count'].sum()
    total_male_authors = len(auth_df[auth_df['gender2'] == 'M'])
    total_female_authors = len(auth_df[auth_df['gender2'] == 'F'])
    total_neutral_authors = len(auth_df[auth_df['gender2'] == 'N'])

    temp = auth_df.drop_duplicates(subset = ['name'])
    unique_authors = len(temp.index)
    unique_male_authors = len(temp[temp['gender2'] == 'M'])
    unique_female_authors = len(temp[temp['gender2'] == 'F'])
    unique_neutral_authors = len(temp[temp['gender2'] == 'N'])

    papers_by_numauthors = bib_df['author count'].value_counts(sort=False)

    average_authors = bib_df['author count'].mean()
    average_authors_per_year = bib_df.groupby(['year'])['author count'].mean()
    total_authors_per_year = bib_df.groupby(['year'])['author count'].sum()

    auth_df_unique = auth_df.drop_duplicates(subset = ['name','year'])
    unique_authors_per_year = auth_df_unique.groupby(['year'])['name'].nunique()
    authors_by_editions = auth_df_unique['name'].value_counts(sort=True)
    authors_with_editions = authors_by_editions.value_counts(sort=False).sort_index()

    temp = auth_df[auth_df['gender2'] == 'M']
    total_male_authors_by_year = temp.groupby(['year']).size()
    temp = auth_df[auth_df['gender2'] == 'F']
    total_female_authors_by_year = temp.groupby(['year']).size()
    temp = auth_df[auth_df['gender2'] == 'N']
    total_neutral_authors_by_year = temp.groupby(['year']).size()
    total_male_percentage_by_year = (100 * total_male_authors_by_year / (total_male_authors_by_year + total_female_authors_by_year))

    temp = auth_df_unique[auth_df_unique['gender2'] == 'M']
    unique_male_authors_by_year = temp.groupby(['year']).size()
    temp = auth_df_unique[auth_df_unique['gender2'] == 'F']
    unique_female_authors_by_year = temp.groupby(['year']).size()
    temp = auth_df_unique[auth_df_unique['gender2'] == 'N']
    unique_neutral_authors_by_year = temp.groupby(['year']).size()
    unique_male_percentage_by_year = (100 * unique_male_authors_by_year / (unique_male_authors_by_year + unique_female_authors_by_year))

    papers_by_authors = auth_df['name'].value_counts(sort=True)
    authors_with_numpapers = papers_by_authors.value_counts(sort=False).sort_index()

    temp = auth_df_unique[auth_df_unique['first'] == True]
    papers_by_authors_first = temp['name'].value_counts(sort=True)
    authors_with_numpapers_first = papers_by_authors_first.value_counts(sort=False).sort_index()

    authors_by_citations = auth_df.groupby(['name'])['citations'].sum().sort_values(ascending=False)
    authors_with_citations = authors_by_citations.value_counts(sort=False).sort_index(ascending=True)

    gender_by_citations = auth_df.groupby(['gender2'])['citations'].sum()
    gender_by_citations_per_year = auth_df.groupby(['gender2','year'])['citations'].sum()

    temp = authfem_df[authfem_df['1F'] == True]
    one_fem = len(temp)
    one_fem_per_year = 100 * temp.groupby(['year']).size() / authfem_df.groupby(['year']).size()

    years = auth_df['year'].unique()
    auth_returning = pd.DataFrame(index = years)
    auth_returning['first_time'] = ''
    auth_returning['returning_other_years'] = ''
    auth_returning['returning_previous_year'] = ''
    auth_returning['total_unique'] = ''
    poolall = []
    poolprevious = []

    for y in years:
        if y == 2001:
            auth_returning.at[y,'returning_previous_year'] = 0
            auth_returning.at[y,'returning_other_years'] = 0
            auth_returning.at[y,'first_time'] = auth_df[auth_df['year'] == y]['name'].nunique()
            auth_returning.at[y,'total_unique'] = auth_df[auth_df['year'] == y]['name'].nunique()
            poolprevious = auth_df[auth_df['year'] == y]['name'].unique()
            poolall = poolprevious
        else:
            temp = auth_df[auth_df['year'] == y]['name'].unique()
            returning = np.intersect1d(temp, poolprevious)
            auth_returning.at[y,'returning_previous_year'] = len(returning)
            returning = np.intersect1d(temp, poolall)
            auth_returning.at[y,'returning_other_years'] = len(returning) - auth_returning.at[y,'returning_previous_year']
            auth_returning.at[y,'first_time'] = len(temp) - auth_returning.at[y,'returning_previous_year'] - auth_returning.at[y,'returning_other_years']
            auth_returning.at[y,'total_unique'] = auth_df[auth_df['year'] == y]['name'].nunique()
            poolprevious = auth_df[auth_df['year'] == y]['name'].unique()
            poolall = np.unique(np.append(poolall,temp))

    # lokta's law fitting
    xdata = np.array(authors_with_numpapers.index)
    ydata = np.array(authors_with_numpapers.values)/(np.array(authors_with_numpapers.values).sum())

    popt, pcov = curve_fit(lotka_law, xdata, ydata)
    residuals = ydata - lotka_law(xdata, *popt)
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((ydata-np.mean(ydata))**2)
    r_squared = 1 - (ss_res / ss_tot)
    #lotka_df = pd.DataFrame(data={'xdata': xdata, 'freq': ydata, 'fit': lotka_law(xdata, *popt)})

    outtxt += '\nTotal authors %d - males %d - females %d - unknown %d' % (total_authors,total_male_authors,total_female_authors,total_neutral_authors)
    outtxt += '\nUnique authors %d - males %d - females %d - unknown %d' % (unique_authors,unique_male_authors,unique_female_authors,unique_neutral_authors)
    outtxt += '\nPapers with at least one female author %d' % one_fem
    outtxt += '\nAverage authors per paper %f' % average_authors
    outtxt += '\nLokta''s law fitting  n %f - C %f - R^2 %f' % (popt[0],popt[1],r_squared)

    with pd.ExcelWriter('./output/authors.xlsx') as writer:
        total_authors_per_year.to_excel(writer, sheet_name='Total authors per year', header=False)
        unique_authors_per_year.to_excel(writer, sheet_name='Unique authors per year', header=False)
        auth_returning.to_excel(writer, sheet_name='Returning authors', header=True)
        average_authors_per_year.to_excel(writer, sheet_name='Avg. auth. per paper per year', header=False)
        total_male_authors_by_year.to_excel(writer, sheet_name='Total male auth. per year', header=False)
        total_female_authors_by_year.to_excel(writer, sheet_name='Total female auth. per year', header=False)
        total_neutral_authors_by_year.to_excel(writer, sheet_name='Total unknown auth. per year', header=False)
        total_male_percentage_by_year.to_excel(writer, sheet_name='Total male auth. % per year', header=False)
        unique_male_authors_by_year.to_excel(writer, sheet_name='Unique male auth. per year', header=False)
        unique_female_authors_by_year.to_excel(writer, sheet_name='Unique female auth. per year', header=False)
        unique_neutral_authors_by_year.to_excel(writer, sheet_name='Unique unknown auth. per year', header=False)
        unique_male_percentage_by_year.to_excel(writer, sheet_name='Unique male % per year', header=False)
        papers_by_numauthors.to_excel(writer, sheet_name='Distr. papers by num authors', header=False)
        papers_by_authors.to_excel(writer, sheet_name='Papers by authors', header=False)
        authors_with_numpapers.to_excel(writer, sheet_name='Distr. authors with #papers', header=False)
        papers_by_authors_first.to_excel(writer, sheet_name='Papers by authors first', header=False)
        authors_with_numpapers_first.to_excel(writer, sheet_name='Authors first with #papers', header=False)
        authors_by_editions.to_excel(writer, sheet_name='Authors at #editions', header=False)
        authors_with_editions.to_excel(writer, sheet_name='Distr. auth. at #editions', header=False)
        authors_by_citations.to_excel(writer, sheet_name='Authors by citations', header=False)
        authors_with_citations.to_excel(writer, sheet_name='Distr. auth. with #citations', header=False)
        gender_by_citations.to_excel(writer, sheet_name='Cit. males-females', header=False)
        gender_by_citations_per_year.to_excel(writer, sheet_name='Cit. males-females per year', header=False)
        one_fem_per_year.to_excel(writer, sheet_name='Papers with >1 female per year', header=False)

    with open('./output/authors.txt', 'w') as text_file:
        text_file.write(outtxt)

    print('\nGenerated authors.txt and authors.xlsx in ./output!')

def stats_affiliation(bib_df, conf_df):

    pa_print.nprint('\nComputing affiliation statistics...')

    outtxt = ''

    auth_df = pd.DataFrame(index=range(bib_df['author count'].sum()), columns=['year','name','citations','institutions','country','continent'])
    mixed_df = pd.DataFrame(index=bib_df.index, columns=['year','institutions','country','continent'])
    j = 0
    for idx, pub in bib_df.iterrows():
        author_count = pub['author count']
        for i in range(author_count):
            auth_df.loc[j,'year']= pub['year']
            auth_df.loc[j,'name'] = pub['author names'][i][0] + ' ' + pub['author names'][i][1]
            auth_df.loc[j,'citations'] = pub['scholar citation count']
            auth_df.loc[j,'institutions'] = pub['institutions'][i]
            auth_df.loc[j,'country'] = pub['countries'][i]
            auth_df.loc[j,'continent'] = pub['continents'][i]
            j = j + 1
        if len(Counter(pub['institutions']).keys()) > 1:
            mixed_df.loc[idx,'institutions'] = True
        else:
            mixed_df.loc[idx,'institutions'] = False
        if len(Counter(pub['countries']).keys()) > 1:
            mixed_df.loc[idx,'country'] = True
        else:
            mixed_df.loc[idx,'country'] = False
        if len(Counter(pub['continents']).keys()) > 1:
            mixed_df.loc[idx,'continent'] = True
        else:
            mixed_df.loc[idx,'continent'] = False
        mixed_df.loc[idx,'year'] = pub['year']

    # when counting - 1 removes the N/A
    number_of_institutions = auth_df['institutions'].nunique() - 1
    number_of_countries = auth_df['country'].nunique() - 1
    number_of_continents = auth_df['continent'].nunique() - 1

    number_of_institutions_per_year = auth_df.groupby(['year'])['institutions'].nunique() - 1
    number_of_countries_per_year = auth_df.groupby(['year'])['country'].nunique() - 1
    number_of_continents_per_year = auth_df.groupby(['year'])['continent'].nunique() - 1

    top_institutions_by_authors = auth_df.groupby(['institutions']).size().sort_values(ascending=False).head(40)
    countries_by_authors = auth_df.groupby(['country']).size().sort_values(ascending=False)
    continents_by_authors = auth_df.groupby(['continent']).size().sort_values(ascending=False)

    top_institutions_by_authorcitations = auth_df.groupby(['institutions'])['citations'].sum().sort_values(ascending=False).head(40)
    countries_by_authorcitations = auth_df.groupby(['country'])['citations'].sum().sort_values(ascending=False)
    continents_by_authorcitations = auth_df.groupby(['continent'])['citations'].sum().sort_values(ascending=False)

    perc_mixed_institute_papers_fraction = 100 * mixed_df[mixed_df['institutions'] == True].shape[0] / mixed_df.shape[0]
    perc_mixed_country_papers_fraction = 100 * mixed_df[mixed_df['country'] == True].shape[0] / mixed_df.shape[0]
    perc_mixed_continent_papers_fraction = 100 * mixed_df[mixed_df['continent'] == True].shape[0] / mixed_df.shape[0]

    temp = mixed_df[mixed_df['institutions'] == True]
    perc_mixed_institute_papers_fraction_per_year = 100 * temp.groupby(['year']).size() / mixed_df.groupby(['year']).size()
    temp = mixed_df[mixed_df['country'] == True]
    perc_mixed_country_papers_fraction_per_year = 100 * temp.groupby(['year']).size() / mixed_df.groupby(['year']).size()
    temp = mixed_df[mixed_df['continent'] == True]
    perc_mixed_continent_papers_fraction_per_year = 100 * temp.groupby(['year']).size() / mixed_df.groupby(['year']).size()

    top_institutions_by_year = auth_df.groupby(['year'])['institutions'].value_counts()
    top_countries_by_year = auth_df.groupby(['year'])['country'].value_counts()
    top_continents_by_year = auth_df.groupby(['year'])['continent'].value_counts()

    years = auth_df['year'].unique()
    perc_authors_diff_country_continent = pd.DataFrame(index = years, columns=['%_same_country_as_conference','%_same_continent_as_conference'])
    for y in years:
        same = len(auth_df[(auth_df['year'] == y) & (auth_df['country'] == conf_df[conf_df['year'] == y]['country'].values[0])].index)
        tot = len(auth_df[(auth_df['year'] == y)].index)
        perc_authors_diff_country_continent.at[y,'%_same_country_as_conference'] = 100 * same/tot
        same = len(auth_df[(auth_df['year'] == y) & (auth_df['continent'] == conf_df[conf_df['year'] == y]['continent'].values[0])].index)
        tot = len(auth_df[(auth_df['year'] == y)].index)
        perc_authors_diff_country_continent.at[y,'%_same_continent_as_conference'] = 100 * same/tot

    outtxt += '\nNumber of institutions %d' % (number_of_institutions - 1)
    outtxt += '\nNumber of countries %d' % (number_of_countries - 1)
    outtxt += '\nNumber of continents %d' % (number_of_continents - 1)
    outtxt += '\nPercentage paper author different institute %f' % perc_mixed_institute_papers_fraction
    outtxt += '\nPercentage paper author different country %f' % perc_mixed_country_papers_fraction
    outtxt += '\nPercentage paper author different coutinent %f' % perc_mixed_continent_papers_fraction

    with pd.ExcelWriter('./output/affiliations.xlsx') as writer:
        number_of_institutions_per_year.to_excel(writer, sheet_name='Num. of auth. instit. per year', header=False)
        number_of_countries_per_year.to_excel(writer, sheet_name='Num. of auth. countr. per year', header=False)
        number_of_continents_per_year.to_excel(writer, sheet_name='Num. of auth. contin. per year', header=False)
        top_institutions_by_authors.to_excel(writer, sheet_name='Top instit. by num authors', header=False)
        countries_by_authors.to_excel(writer, sheet_name='Dist. count. by num authors', header=False)
        continents_by_authors.to_excel(writer, sheet_name='Dist. contin. by num authors', header=False)
        top_institutions_by_authorcitations.to_excel(writer, sheet_name='Top instit. by auth. cit.', header=False)
        countries_by_authorcitations.to_excel(writer, sheet_name='Dist. countr. by auth. cit.', header=False)
        continents_by_authorcitations.to_excel(writer, sheet_name='Dist. contin. by auth. cit.', header=False)
        perc_mixed_institute_papers_fraction_per_year.to_excel(writer, sheet_name='% paper mixed instit. per year', header=False)
        perc_mixed_country_papers_fraction_per_year.to_excel(writer, sheet_name='% paper mixed countr. per year', header=False)
        perc_mixed_continent_papers_fraction_per_year.to_excel(writer, sheet_name='% paper mixed contin. per year', header=False)
        perc_authors_diff_country_continent.to_excel(writer, sheet_name='% auth. from out conf. per year', header=True)
        top_institutions_by_year.to_excel(writer, sheet_name='Top instit. by year', header=False)
        top_countries_by_year.to_excel(writer, sheet_name='Top count. by year', header=False)
        top_continents_by_year.to_excel(writer, sheet_name='Top contin. by year', header=False)

    with open('./output/affiliations.txt', 'w') as text_file:
        text_file.write(outtxt)

    print('\nGenerated affiliations.txt and affiliations.xlsx in ./output!')

def stats_travel(bib_df, conf_df):

    pa_print.nprint('\nComputing travel statistics...')

    outtxt = ''

    trav_df = pd.DataFrame(index=bib_df.index, columns=['year','distance','footprint','country','continent','gender'])
    for idx, pub in bib_df.iterrows():
        trav_df.loc[idx,'year'] = pub['year']
        trav_df.loc[idx,'distance'] = pub['author distances'][0]
        trav_df.loc[idx,'footprint'] = pub['author footprints'][0]
        trav_df.loc[idx,'country'] = pub['countries'][0]
        trav_df.loc[idx,'continent'] = pub['continents'][0]
        trav_df.loc[idx,'gender'] = pub['author genders 2'][0]

    trav_df = trav_df.convert_dtypes()

    total_distance = trav_df['distance'].sum()
    total_footprint = trav_df['footprint'].sum()
    average_distance = trav_df['distance'].mean()
    average_footprint = trav_df['footprint'].mean()

    total_distance_per_year = trav_df.groupby(['year'])['distance'].sum()
    total_footprint_per_year = trav_df.groupby(['year'])['footprint'].sum()
    average_distance_per_year = trav_df.groupby(['year'])['distance'].mean()
    average_footprint_per_year = trav_df.groupby(['year'])['footprint'].mean()

    average_distance_per_continent = trav_df.groupby(['continent'])['distance'].mean()
    average_footprint_per_continent = trav_df.groupby(['continent'])['footprint'].mean()

    average_distance_per_country = trav_df.groupby(['country'])['distance'].mean().sort_values(ascending=False)
    average_footprint_per_country = trav_df.groupby(['country'])['footprint'].mean().sort_values(ascending=False)

    average_distance_per_gender = trav_df.groupby(['gender'])['distance'].mean()
    average_footprint_per_gender = trav_df.groupby(['gender'])['footprint'].mean()

    participants_by_country = trav_df.groupby(['country'])['footprint'].count().sort_values(ascending=False)
    participants_by_country_per_year = trav_df.groupby(['year','country'])['footprint'].count()

    outtxt += '\nTotal distance %f' % total_distance
    outtxt += '\nTotal footprint %f' % total_footprint
    outtxt += '\nAverage distance per participant %f' % average_distance
    outtxt += '\nAverage footprint per participant %f' % average_footprint

    with pd.ExcelWriter('./output/travel.xlsx') as writer:
        total_distance_per_year.to_excel(writer, sheet_name='Total dist. per year', header=False)
        total_footprint_per_year.to_excel(writer, sheet_name='Total dist. per year', header=False)
        average_distance_per_year.to_excel(writer, sheet_name='Avg. dist. per part. per year', header=False)
        average_footprint_per_year.to_excel(writer, sheet_name='Avg. footp. per part. per year', header=False)
        average_distance_per_continent.to_excel(writer, sheet_name='Avg. dist. per part. by cont.', header=False)
        average_footprint_per_continent.to_excel(writer, sheet_name='Avg. footp. per part. by cont.', header=False)
        average_distance_per_country.to_excel(writer, sheet_name='Avg. dist. per part. by count.', header=False)
        average_footprint_per_country.to_excel(writer, sheet_name='Avg. footp. per part. by count.', header=False)
        average_distance_per_gender.to_excel(writer, sheet_name='Avg. dist. per part. by gender', header=False)
        average_footprint_per_gender.to_excel(writer, sheet_name='Avg. footp. per part. by gender', header=False)
        participants_by_country.to_excel(writer, sheet_name='Participants by count.', header=False)
        participants_by_country_per_year.to_excel(writer, sheet_name='Participants by count. per year', header=False)

    with open('./output/travel.txt', 'w') as text_file:
        text_file.write(outtxt)

    print('\nGenerated travel.txt and travel.xlsx in ./output!')

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

    answer = boolify(input("\nGenerate papers statistics? (y/N): "))
    if answer:
        stats_papers_out = stats_papers(bib_df)

    answer = boolify(input('\nGenerate authorship statistics? (y/N): '))
    if answer:
            stats_authors_out = stats_authors(bib_df)

    answer = boolify(input('\nGenerate affiliation statistics? (y/N): '))
    if answer:
        stats_affiliation_out = stats_affiliation(bib_df, conf_df)

    answer = boolify(input('\nGenerate travel statistics? (y/N): '))
    if answer:
        stats_travel_out = stats_travel(bib_df, conf_df)
