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
import time
import random
import re
import datetime
import itertools
import requests

# External
import orjson
import unidecode
from opencage.geocoder import OpenCageGeocode
from tqdm import tqdm

# Helper
import pa_print
from pa_utils import try_index

geocoder = OpenCageGeocode('c55bcffbb38246aab6e54c136a5fac75')
email_regex = re.compile(r'@[a-zA-Z0-9-–]+\.[a-zA-Z0-9-–.]+')

def scholar_api_paper_search(query,key,sleep):
    api = 'https://api.semanticscholar.org/graph/v1/paper/search?query='
    fields = '&fields=authors,title,year,citationCount,influentialCitationCount'
    if key != '':
        api_key = '&x-api-key='+key
        query_result = requests.get(api+query+fields+api_key).json()
        time.sleep(sleep)
    else:
        query_result = requests.get(api+query+fields).json()
        time.sleep(0.06) # default max 5000 requests per 5 minute
    return query_result

def scholar_api_paper_lookup(paper_id,key,sleep):
    api = 'https://api.semanticscholar.org/graph/v1/paper/'
    cit = 'citations.authors,citations.title,citations.year,citations.s2FieldsOfStudy,citations.publicationTypes,citations.journal,citations.publicationVenue'
    ref = 'references.authors,references.title,references.year,references.s2FieldsOfStudy,references.publicationTypes,references.journal,references.publicationVenue'
    fields = '?fields=title,authors,paperId,embedding,s2FieldsOfStudy,publicationTypes,publicationVenue,tldr,'+cit+','+ref             
    if key != '':
        api_key = '&x-api-key='+key
        query_result = requests.get(api+paper_id+fields+api_key).json()
        time.sleep(sleep)
    else:
        query_result = requests.get(api+paper_id+fields).json()
        time.sleep(0.06) # default max 5000 requests per 5 minute
    return query_result

def request_scholar(pub, args):
    ''' Queries citations from Semantic Scholar

    :publication from bibtex file
    '''
    try:
        with open('./cache/json/scholar_cache.json','rb') as fp:
            scholar_cache = orjson.loads(fp.read())
    except FileNotFoundError:
        pa_print.tprint('\nCreating new Semantic Scholar cache!')
        scholar_cache = {}

    # Fix names for searching
    regextitle = re.compile(r'[^a-zA-Z0-9 ]')
    regexname = re.compile(r'[^a-zA-Z- ]')
    author_last_list = []

    for _, (_, last) in enumerate(pub['author names']):
        last = last.split('-')[-1]
        author_last_list.append(last)

    title = unidecode.unidecode(pub['title'])

    if args.nime:
        if title == 'Now': # title is too short, this return other paper, trying to filter it out by forcing full author name
            author_last_list[0] = 'GarthPaine'

    pub['scholar query'] = 'N/A'
    pub['scholar citation count'] = 'N/A'
    pub['scholar influential citation count'] = 'N/A'
    pub['scholar reference count'] = 'N/A'
    pub['scholar paper id'] = 'N/A'
    pub['scholar title'] = 'N/A'
    pub['scholar authors id'] = ['N/A']*len(pub['author names'])
    pub['scholar embedding'] = {}
    pub['scholar tldr'] = {}
    pub['scholar field of study'] = []
    pub['scholar publication venue'] = {}
    pub['scholar publication type'] = []
    pub['scholar references'] = []
    pub['scholar citations'] = []
    pub['scholar references'] = []
    pub['scholar valid'] = False
    pub['scholar field of study'] = []
    pub['scholar publication venue'] = []
    pub['scholar publication type'] = []


    # Make query title, name and year lists
    query_title = list(dict.fromkeys([title, regextitle.sub('', title), ' '.join([w for w in title.split() if len(w)>1])]))
    if len(author_last_list) > 1:
        query_name = [' '.join(author_last_list), author_last_list[0], '']
    else:
        query_name = [author_last_list[0], '']
    query_year = ['', pub['year']]

    # Save query to be used for cache
    full_query = f"{title} {' '.join(author_last_list)} {pub['year']}"
    pub['scholar query'] = full_query

    if full_query not in scholar_cache:
        pa_print.tprint(f'\nQuerying Semantic Scholar...')
        last_iter = False
        lookup_result = {}
        queries = list(itertools.product(query_title, query_name, query_year))
        num_of_queries = len(queries)
        
        for idx,temp in enumerate(queries):
            
            # Checking if last query
            if idx == (num_of_queries - 1):
                last_iter = True

            # Generate new query from combination
            temp_title, temp_author, temp_year = temp[0], temp[1], temp[2]
            scholar_query = f'{temp_title} {temp_author} {temp_year}'

            # Try query
            pa_print.tprint(f"Trying query: '{scholar_query}'")
            try:
                query_result = scholar_api_paper_search(scholar_query,args.sskey,args.sleep)
            except Exception as e:
                query_result = {'results' : {}}
                err_info = 'x - While querying Semantic Scholar an exception of type {0} occurred.\nArguments:\n{1!r}.'
                err_msg = err_info.format(type(e).__name__, e.args)
                pa_print.tprint(err_msg)
            
            if not 'error' in query_result.keys() and 'data' in query_result and len(query_result['data']) > 0:
                if ('citationCount' in query_result['data'][0] or last_iter) and len(query_result['data'][0]['authors']) <= (len(author_last_list) + 1):
                    result_author = ' '.join([t['name'] for t in query_result['data'][0]['authors']])
                    result_author = regexname.sub('', unidecode.unidecode(result_author)).lower()
                    query_author = regexname.sub('', author_last_list[0].lower().split(' ')[-1])

                    if result_author.find(query_author) != -1:
                        # if paper never cited, creating citation fields and setting to 0 
                        if ('citationCount' not in query_result['data'][0]):
                            query_result['data'][0]['citationCount'] = 0
                            query_result['data'][0]['influentialCitationCount'] = 0

                        pub['scholar citation count'] = query_result['data'][0]['citationCount']
                        pub['scholar influential citation count'] = query_result['data'][0]['influentialCitationCount']
                        pub['scholar paper id'] = query_result['data'][0]['paperId']
                        pub['scholar title'] = query_result['data'][0]['title']
                        pub['scholar authors id'] = [t['authorId'] for t in query_result['data'][0]['authors']]
                        scholar_cache[full_query] = query_result

                        if pub['scholar paper id'] not in scholar_cache:
                            pa_print.tprint(f'\nSemantic Scholar paper lookup...')
                            lookup_result = scholar_api_paper_lookup(pub['scholar paper id'],args.sskey,args.sleep)
                            if 'message' not in lookup_result:
                                scholar_cache[pub['scholar paper id']] = lookup_result
                        else:
                            lookup_result = scholar_cache[pub['scholar paper id']]
                        
                        pa_print.tprint(f"✓ - Paper has been cited {pub['scholar citation count']} times")

                        break

        if pub['scholar citation count'] == 'N/A':
            pa_print.tprint('x - Cannot find paper in Semantic Scholar')
            #scholar_cache[full_query] = 'N/A'

        with open('./cache/json/scholar_cache.json','wb') as fp:
            fp.write(orjson.dumps(scholar_cache))

    else:
        if scholar_cache[full_query] != 'N/A':
            pub['scholar citation count'] = scholar_cache[full_query]['data'][0]['citationCount']
            pub['scholar influential citation count'] = scholar_cache[full_query]['data'][0]['influentialCitationCount']
            pub['scholar paper id'] = scholar_cache[full_query]['data'][0]['paperId']
            pub['scholar title'] = scholar_cache[full_query]['data'][0]['title']
            pub['scholar authors id'] = [t['authorId'] for t in scholar_cache[full_query]['data'][0]['authors']]
            if 'embedding' in scholar_cache[pub['scholar paper id']]:
                pub['scholar embedding'] = scholar_cache[pub['scholar paper id']]['embedding']
            if 'tldr' in scholar_cache[pub['scholar paper id']]:
                pub['scholar tldr'] = scholar_cache[pub['scholar paper id']]['tldr']
            if 'citations' in scholar_cache[pub['scholar paper id']]:
                pub['scholar citations'] = scholar_cache[pub['scholar paper id']]['citations']
            if 'references' in scholar_cache[pub['scholar paper id']]:
                pub['scholar references'] = scholar_cache[pub['scholar paper id']]['references']
                pub['scholar reference count'] = len(scholar_cache[pub['scholar paper id']]['references'])
                if pub['scholar reference count'] > 0:
                    pub['scholar valid'] = True

            if pub['scholar paper id'] not in scholar_cache:
                pa_print.tprint(f'\nSemantic Scholar paper lookup...')
                lookup_result = scholar_api_paper_lookup(pub['scholar paper id'],args.sskey,args.sleep)
                scholar_cache[pub['scholar paper id']] = lookup_result
            else:
                lookup_result = scholar_cache[pub['scholar paper id']]

        pa_print.tprint(f"\no - Retrieved from cache: {pub['scholar citation count']} citations")

    if lookup_result:
        if 'embedding' in lookup_result:
            pub['scholar embedding'] = lookup_result['embedding']
        if 'tldr' in lookup_result:
            pub['scholar tldr'] = lookup_result['tldr']
        if 's2FieldsOfStudy' in lookup_result:
            pub['scholar field of study'] = lookup_result['s2FieldsOfStudy']
        if 'publicationTypes' in lookup_result:
            pub['scholar publication venue'] = lookup_result['publicationVenue']
        if 'publicationTypes' in lookup_result:
            pub['scholar publication type'] = lookup_result['publicationTypes']
        if 'citations' in lookup_result:
            pub['scholar citations'] = lookup_result['citations']
        if 'references' in lookup_result:
            pub['scholar references'] = lookup_result['references']
            pub['scholar reference count'] = len(lookup_result['references'])
            if pub['scholar reference count'] > 0:
                pub['scholar valid'] = True

    # Average citations per year of age
    if pub['scholar citation count'] != 'N/A':
        if pub['age'] == 0:
            pub['age'] = 1
        pub['scholar yearly citations'] = int(pub['scholar citation count']) / pub['age']
    else: pub['scholar yearly citations'] = 'N/A'

def request_location(author_info, args, pub):
    ''' Extracts location from author blocks or universities and queries OpenCageGeocode

    :publication from bibtex file
    '''
    author_count = pub['author count']

    # Conference location lookup
    cnf_query = pub['address']
    query_type = 'conference'

    query_location(cnf_query, query_type, pub, args) # *** creates unneeded columns ***

    # Author location lookup
    for author in range(author_count): # length of usable locations
        query_type = 'author'

        # Assign one query (in order of priority)
        # 1) If there is a university address from grobid
        if pub['grobid author unis'][author] != 'N/A': # uni address
            location_query = ', '.join(pub['grobid author unis'][author]) # (uni name, country)
            query_origin = 'grobid uni'

        # 2) If grobid was used to add address (while 'location' is api derived)
        elif pub['grobid addresses'][author] != 'N/A':
            location_query = pub['grobid addresses'][author]
            query_origin = 'grobid address'

        # 3) If theres a uni address from text block
        elif pub['text author unis'][author] != 'N/A':
            location_query = ', '.join(pub['text author unis'][author]) # (uni name, country)
            query_origin = 'text uni'

        # 4) Else, scrape from raw author block (which may or may not have email)
        elif author < len(author_info) and author_info[author] != 'N/A': # check if author_info contains author 'i' and is non-empty
            auth_block = author_info[author]
            cut_line = -1 if '@' in auth_block else 0 # one line above if email present
            info_lines = auth_block.split('\n')
            location_query = ' '.join(info_lines[cut_line-1:cut_line])
            if len([line for line in location_query if line.isdigit()]) > 8: # look for tele #
                location_query = ' '.join(info_lines[cut_line-2:cut_line-1]) # take line higher if telephone
            query_origin = 'raw author block'

        else:
            location_query = 'N/A'
            query_origin = 'No query'
            pa_print.tprint("\nCouldn't find a location to use!")

        pa_print.tprint(f'\nLooking for: {location_query}')
        pub['author loc queries'].append(location_query)
        pub['author query origins'].append(query_origin)
        query_location(location_query, query_type, pub, args)

def query_location(location_query, query_type, pub, args): # 'query_type is now only used to print status
    # Load cache
    try:
        with open('./cache/json/location_cache.json','rb') as fp:
            location_cache = orjson.loads(fp.read())
    except FileNotFoundError:
        pa_print.tprint('\nCreating new location cache!')
        location_cache = {'N/A': 'N/A'}

    # Not cached
    if location_query not in location_cache:
        try:
            geocoder = OpenCageGeocode(args.ockey)
            # OpenCageGeocode: 2,500 req/day, 1 req/s - https://github.com/OpenCageData/python-opencage-geocoder
            location = geocoder.geocode(location_query, language='en', limit=1, no_annotations=1, no_record=1)[0]
            # Format result
            geometry = location['geometry'] # lat/long
            components = location['components'] # fine loc info
            location_info = (location['formatted'],
                            (components['country'], components['continent']),
                            (geometry['lat'], geometry['lng']),
                            location['confidence']) # 1 (>25km) to 10 (<0.25km)

            location_cache[location_query] = location_info
            pub[f'{query_type} location info'].append(location_info[:3]) # add all location into one column
            pub[f'{query_type} location confidence'].append(location_info[3]) # confidence in separate column
            pa_print.tprint(f'✓ - Parsed {query_type} location: {location_info[0]}')
            time.sleep(1+random.random())

        except Exception as e: # API fails    
            #location_cache[location_query] = 'N/A'
            pub[f'{query_type} location info'].append('N/A')
            pub[f'{query_type} location confidence'].append('N/A')
            err_info = 'x - Could not parse {0} location: {1}, while querying Open Cage Data an exception of type {2} occurred.\nArguments:\n{3!r}.'
            err_msg = err_info.format(query_type,location_query,type(e).__name__, e.args)
            pa_print.tprint(err_msg)
        
        # Save changes to cache
        with open('./cache/json/location_cache.json','wb') as fp:
            fp.write(orjson.dumps(location_cache))

    # Cached
    else:
        if location_cache[location_query] != 'N/A' and not (location_query == 'N/A'):
            location_info = location_cache[location_query]
            pub[f'{query_type} location info'].append(location_info[:3])
            pub[f'{query_type} location confidence'].append(location_info[3])
            pa_print.tprint(f'o - Cached {query_type} location: {location_info[0]}')

        else:
            location_info = 'N/A'
            pub[f'{query_type} location info'].append('N/A')
            pub[f'{query_type} location confidence'].append('N/A')
            pa_print.tprint(f'o - Null {query_type} location: {location_info}')

def request_uni(unidomains, author_info, args, pub):
    ''' Extract university from email handle

    :publication from bibtex file
    '''
    pub_matches = 0
    grob_matches = 0
    text_matches = 0

    author_count = pub['author count']

    # Internal functions for lookup in unidomains.json
    def lookup_uni (handle, email_type, pub):
        nonlocal pub_matches
        for uni in unidomains:
            if handle in uni['domains']:
                pub[f'{email_type} author unis'].append((uni['name'], uni['country']))
                pub_matches += 1
                uni_match = True
                break

    def handle_check(email, email_type, pub):
        handle = email.split("@")[-1].strip()

        # Look for handle in json, split once by dot and retry if not found
        uni_match = False
        lookup_uni(handle, email_type, pub)
        while uni_match == False and handle.count('.') > 1:
            handle = handle.split('.', 1)[-1]
            lookup_uni(handle, email_type, pub)

    # 1) Using grobid derived emails to choose handle
    email_type = 'grobid'
    for author in range(author_count):
        email = pub['grobid emails'][author]
        if email != 'N/A': # check for valid email
            handle_check(email, email_type, pub)

    grob_matches = pub_matches

    # 2) Using scraped author info block from header if not enough emails
    if len(author_info) > 0 and (grob_matches < author_count):
        email_type = 'text'
        for author in author_info: # ! could be more authors than exit
            info_emails = email_regex.findall(author) # look for '@handle.tld' in block
            for _, email in enumerate(info_emails): # case: multiple emails are within an author block #! (will overwrite)
                if email != 'N/A':
                    handle_check(email, email_type, pub)

    # Fill in missing unis with 'N/A' # ! author block not linked in order with authors
    for type, author in [(type, author) for type in ['grobid', 'text'] for author in range(author_count)]:
        try:
            pub[f'{type} author unis'][author]
        except IndexError:
            pub[f'{type} author unis'].append('N/A')

    text_matches = pub_matches - grob_matches
    pub_matches = max(text_matches, grob_matches)

    pa_print.tprint(f'o - Found {pub_matches} uni\'s from email handles\n')
