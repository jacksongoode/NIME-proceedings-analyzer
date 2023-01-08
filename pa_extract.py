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
import os
import re
import requests
from unidecode import unidecode
import datetime

# External
from pdfminer.pdfparser import PDFParser, PSSyntaxError
from pdfminer.pdfdocument import PDFDocument
from pdfminer.high_level import extract_text as extract_pdf
from pdfminer.pdfinterp import resolve1
from pdfminer.layout import LAParams

import fasttext
fasttext.FastText.eprint = lambda x: None # do not display warning message
import gender_guesser.detector as gender # https://github.com/lead-ratings/gender-guesser
import onomancer as ono # https://github.com/parthmaul/onomancer

import nltk
#from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.stem.porter import PorterStemmer
from nltk.tokenize import sent_tokenize, word_tokenize

from gensim.parsing.preprocessing import STOPWORDS

from bs4 import BeautifulSoup
from tqdm import tqdm
import orjson
import pikepdf

# Helper
import pa_print
from pa_load import check_xml

# Variables
pdf_src = os.getcwd()+'/cache/pdf/'
xml_src = os.getcwd()+'/cache/xml/'
jats_src = os.getcwd()+'/cache/jats/'
text_src = os.getcwd()+'/cache/text/'
gg = gender.Detector()

# Compile regular expressions
auth_regex = re.compile(r'(?:^[A-Z |].+$)(?:\s^[\S |].+$)*\s(?:.+@[a-zA-Z0-9-–]+\.[a-zA-Z0-9-–.]+)', re.M)
abst_regex = re.compile(r'^\s*(?:Abstract|ABSTRACT)\s*$', re.M)
intro_regex = re.compile(r'^[0-9]?.?\s*(?:Introduction|INTRODUCTION).*$', re.M)
ackn_regex = re.compile(r'^[0-9]?.?\s*(?:Acknowledg[e]?ment[s]?|ACKNOWLEDG[E]?MENT[S]?)\s*$', re.M)
ref_regex = re.compile(r'^[0-9]?.?\s*(?:References|REFERENCES)\s*$', re.M)
regex_list = (abst_regex, intro_regex, ackn_regex, ref_regex)

def extract_bib(pub, args):
    ''' Extracts and expands data found in bibtex entry

    :publication (article) from database
    '''
    # Basic info from authors
    authors = pub['author'].split(' and ')
    author_count = len(authors)
    pub['author count'] = author_count

    bad_names = ['professor', 'dr.'] # names to remove
    allowed_names = ['d\'', 'di', 'da', 'de', 'do', 'du', 'des', 'af', 'von', 'van', 'los', 'mc', 'of', 'zu']
    regexname = re.compile(r'[^a-zA-Z- ]')

    for _, author in enumerate(authors): # break up names
        first = unidecode(author.split(', ', 1)[-1] if ', ' in author else author.split(' ', 1)[0])
        last = unidecode(author.split(', ', 1)[0] if ', ' in author else author.split(' ', 1)[-1])

        # First name
        first = [part for part in first.split(' ')
                if not ((len(part) > 2 and '.' in part)
                or part.lower() in bad_names)] # remove names with length > 2 followed by full stop, and bad names
        if not first:
            first = '' # if list is empty
        else:
            first = first[0] # only one first name

        first = regexname.sub('', first)

        # Last name
        if last[:2].lower() != 'd\'':
            last = [part for part in last.split(' ') if not part.lower() in bad_names]
            if str.lower(last[0]) in allowed_names:
                last = ' '.join(last)
            elif ('.' in last[-1]) or (len(last[-1])==1): # if initial, remove
                last = last[0]
            else:
                last = last[-1]

            last = regexname.sub('', last)

        # Capitalize
        # check for length, exclude if first letter cap, but not whole word cap
        if len(first) > 0:
            if not first[0].isupper() or first.isupper():
                first = first.title()
        if len(last) > 0:
            if not last[0].isupper() or last.isupper():
                last = last.title()

        if args.nime:
            # Unique names
            if (first == 'Woon' and last == 'Seung Yeo') or (first == 'Woon' and last == 'Yeo'):
                first = 'Woonseung'
                last = 'Yeo'
            elif (first == 'R' and last == 'Knapp'):
                first = 'Benjamin'
                last = 'Knapp'
            elif (first == 'Joe' and last == 'Paradiso'):
                first = 'Joseph'
                last = 'Paradiso'
            elif (first == 'Martin' and last == 'Naef'):
                last = 'Naf'
            elif (first == 'Cornelius' and last == 'Poepel'):
                last = 'Popel'
            elif (first == 'Misra' and last == 'Ananya'):
                last = 'Misra'
            elif (first == 'Alfonso' and last == 'Carrillo'):
                last = 'Perez'

        pub['author names'].append((first, last))

        # Guess gender by first name
        gender_1 = gg.get_gender(first)
        gender_2 = next(iter(ono.predict(first).values()))

        if args.nime:
            # Manual amend gender for NIME authors with gender 2 = N
            if (first == 'Tone' and last == 'Ase') or \
            (first == 'Ye' and last == 'Pan') or \
            (first == 'Rumi' and last == 'Hiraga') or \
            (first == 'Quinn' and last == 'Holland') or \
            (first == 'Eri' and last == 'Kitamura'):
                gender_1 = 'female'
                gender_2 = 'F'

            if (first == 'Woonseung' and last == 'Yeo') or \
            (first == 'Yu' and last == 'Nishibori') or \
            (first == 'Jimin' and last == 'Jeon') or \
            (first == 'Leshao' and last == 'Zhang') or \
            (first == 'Michal' and last == 'Seta') or \
            (first == 'Joung' and last == 'Han') or \
            (first == 'Kuljit' and last == 'Bhamra'):
                gender_1 = 'male'
                gender_2 = 'M'

        pub['author genders'].append(gender_1) # gender_guesser (m, mostly_m, andy, mostly_f, f, unknown)
        pub['author genders 2'].append(gender_2) # onomancer (m, f)

    # Page count
    page_count = pub.get('pages')
    try:
        page_count = page_count.split('--')
        page_count = int(page_count[1]) - int(page_count[0]) + 1
        pub['page count'] = int(page_count)
    except:
        pub['page count'] = 'N/A'

    # Check if in NIME Reader
    with open('./resources/nime_reader.txt','r') as f:
        nime_reader = f.readlines()
    nime_reader = [line.strip() for line in nime_reader]
    pub['NIME reader'] = 'No'
    for i in nime_reader:
        if i == pub['title']:
            pub['NIME reader'] = 'Yes'

    # Age of papers
    pub['age'] = datetime.datetime.now().year - int(pub['year'])

def download_pdf(pdf_path, pub):
    pa_print.tprint('\nLocal PDF not found - downloading...')
    url = pub['url']
    r = requests.get(url, allow_redirects=True)
    open(pdf_path, 'wb').write(r.content)

def download_xml(xml_path, pub):
    pa_print.tprint('\nLocal PubPub XML not found - downloading...')
    url = pub['url']
    r = requests.get(url, allow_redirects=True)
    url = re.search(r"jats&quot;,&quot;url&quot;:&quot;(.*?.xml)", r.text).group(1)

    r = requests.get(url, allow_redirects=True)
    open(jats_src, 'wb').write(r.content)

def extract_text(pub):
    '''Extracts text content from pdf using pdfminer.six, downloads pdf if non-existant

    :publication (article) from database
    '''
    pdf_fn = pub['url'].split('/')[-1]
    pdf_path = pdf_src + pdf_fn

    # Allows for override of corrupted pdfs
    if os.path.isfile(pdf_path):
        pass
    else: # doesnt exist - download
        download_pdf(pdf_path, pub)

    # Page count for those without
    if pub['page count'] == 'N/A':
        pdf = open(pdf_path, 'rb')
        check = False
        while True: # try once
            try:
                parser = PDFParser(pdf)
                document = PDFDocument(parser)
            except Exception as e:
                if check is True:
                    raise PSSyntaxError(f'{pdf_path} appears to be malformed and pdf cannot repair it.')
                pa_print.tprint(str(e))
                pa_print.tprint(f'Attempting to repair {pdf_path}')
                pike = pikepdf.Pdf.open(pdf_path, allow_overwriting_input=True)
                pike.save(pdf_path)
                check = True
                continue
            break

        pub['page count'] = resolve1(document.catalog['Pages'])['Count']

    fn = pdf_fn.split('.')[0]
    miner_text_file = f'{text_src}miner/miner_{fn}.txt'

    # Read miner text if exists
    if os.path.isfile(miner_text_file):
        with open(miner_text_file, 'r') as f:
            doc = f.read()
            return doc

    else: # if not, make them
        pa_print.tprint(f'\nExtracting: {pdf_fn}')

        laparams = LAParams()
        setattr(laparams, 'all_texts', True)
        doc = extract_pdf(pdf_path, laparams=laparams)

        with open(miner_text_file, 'w') as f:
            f.write(doc)

        return doc

def extract_grobid(pub, bib_db, iterator):
    '''Parse xml files output from Grobid service (3rd party utility needed to generate files)

    :publication (article) from database
    '''
    def elem_text(elem, fill='N/A'): # to get element text w/o error
        if elem:
            return elem.getText(separator=' ', strip=True)
        else:
            return fill

    if pub['puppub']:
        xml_name = f"nime{pub['year']}_{pub['articleno']}.xml"
    else:
        xml_name = pub['url'].split('/')[-1].split('.')[0]+'.tei.xml'

    xml_path = xml_src + xml_name

    if os.path.exists(xml_path):
        with open(xml_path, 'r') as tei:
            soup = BeautifulSoup(tei, "lxml-xml")

        if soup.analytic is None:
            pa_print.tprint(f'\n{xml_name} is empty!')
            return

        pa_print.tprint(f'\nParsing through grobid XML of {xml_name}')

        grob_names, grob_emails, grob_orgs, grob_addrs  = [], [], [], []

        # Begin with parsing author info
        authors = soup.analytic.find_all('author')

        for author in authors:
            persname = author.persname
            if persname:
                firstname = elem_text(persname.find("forename", type="first"), '')
                middlename = elem_text(persname.find("forename", type="middle"), '')
                surname = elem_text(persname.surname, '') # *** should this be find? ***
                name = (firstname, middlename, surname)
                grob_names.append(name)

            grob_emails.append(elem_text(author.email))

        # There's an issue where affils can be within an <author> alongside an author or independently
        # authors = [author for author in authors if not author.affiliation]
        affils = [author for author in authors if author.affiliation]
        for affil in affils:
            grob_orgs.append(elem_text(affil.orgname))
            grob_addrs.append(elem_text(affil.address))

        grob_info = [grob_names, grob_emails, grob_orgs, grob_addrs]

        # Fill in missing data with 'N/A'
        author_count = pub['author count']
        for author in range(author_count):
            for info in grob_info:
                try:
                    info[author]
                except IndexError:
                    info.append('N/A')

        # Add info to df - merge everything!
        pub['grobid author names'].extend(grob_names) # to check who appeared in grobid info
        pub['grobid emails'].extend(grob_emails)
        pub['grobid organisations'].extend(grob_orgs)
        pub['grobid addresses'].extend(grob_addrs)

        # Extract meaningful text using grobid tags (within p tags) and save to txt
        grob_text_file = f"{text_src}grobid/grob_{xml_name.split('.')[0]}.txt"
        if os.path.isfile(grob_text_file): # check if txt already exists
            with open(grob_text_file, 'r') as f:
                grob_text = f.read()
        else:
            # ! This needs to be a little more sophisticated
            # PubPub tei's have expansive body
            # /n and spaces need to be addressed
            grob_text = []
            grob_body = soup.body.find_all('p')
            for p in grob_body:
                p = re.sub(r'\s+', ' ', elem_text(p)).strip()
                grob_text.append(p)
            grob_text = str(grob_text)
            with open(grob_text_file, 'w') as f:
                f.write(grob_text)

        return grob_text
    elif os.path.exists(f"./cache/pdf/unconvertable_pdfs/{xml_name.split('.')[0]}.pdf"):
        pass
    else: # No XML - populate
        pa_print.tprint('\nGrobid XML does not exist for paper!')
        if pub['puppub']:
            check_xml(bib_db, jats=True)
        else:
            check_xml(bib_db)
        iterator.clear()
        iterator.refresh()

def extract_author_info(doc, pub):
    ''' Searches through pdf text for author block using regex (no Grobid needed)

    :document from text extraction (miner) or xml extraction (grobid)
    :publication (article) from database
    '''
    pa_print.tprint('\nExtracting authors from paper...')

    author_info = []
    author_count = pub['author count']

    # * Method 1 - Look for block with email tail (bibtex not needed, more robust)
    author_info = auth_regex.findall(doc)[:author_count] # grab only up to total authors

    if len(author_info) != 0:
        pa_print.tprint('✓ - Found by block')

    # * Method 2 - Look for block starting with author name (bibtex needed)
    else:
        for author in range(author_count): # only look up to i authors
            author_first = pub['author names'][author][0]
            author_last = pub['author names'][author][1]
            pa_print.tprint(f'\nLooking for: {author_first} {author_last}')

            author_first = author_first.replace('\\', '') # fixes issues with regex
            author_last = author_last.replace('\\', '')

            name_regex = r'(?:^.*'+author_first+r'.+'+author_last+r'.*$)(?:\s^[\S |].+$)*'
            author_search = re.search(name_regex, doc, re.M)
            try:
                author_info.append(author_search.group(0))
                pa_print.tprint('✓ - Found by name')
            except:
                pa_print.tprint('x - No match by name')

    pa_print.tprint(f'\n✓ - Found {len(author_info)} author(s) in paper of {author_count} total')

    # If there were a different number of authors from text block
    if len(author_info) < author_count:
        pub['author block mismatch'] = 'Too few'
    elif len(author_info) > author_count:
        pub['author block mismatch'] = 'Too many'

    # Add 'N/A' for missing authors # ! Note: Author block will not correspond in order to authors
    authors_missed = author_count - len(author_info)
    pub['author block missed'] = authors_missed
    for author in range(authors_missed):
        author_info.append('N/A')

    # Add for visibility with csv - # ! but may not be the best idea if processing afterwards
    pub['author infos'] = '\n\n'.join(author_info)

    return author_info

def trim_headfoot(doc, pub=None):
    ''' Trim the header and footer from extracted text (unused and inferior to Grobid service)

    :document from text extraction (miner) or xml extraction (grobid)
    '''
    # Function for trimming header and footer
    # Remove until abstract or introduction
    pdf_trimmed = abst_regex.split(doc, 1)
    if len(pdf_trimmed) == 1:
        pdf_trimmed = intro_regex.split(pdf_trimmed[0], 1) # if no abstract, use 'introduction'
        if len(pdf_trimmed) == 1:
            pdf_trimmed = pdf_trimmed[0]
            if pub is not None: pub['header fail'] = 'X'
            pa_print.tprint('Could not split header during parsing!')
        else:
            pdf_trimmed = pdf_trimmed[1]
            # pa_print.tprint('Split header at intro')
    else:
        pdf_trimmed = pdf_trimmed[1]
        # pa_print.tprint('Split header at abstract')
    # return pdf_trimmed

    # Remove after references or acknowledgements
    pdf_slimmed = ackn_regex.split(pdf_trimmed, 1)
    if len(pdf_slimmed) == 1:
        pdf_slimmed = ref_regex.split(pdf_slimmed[0], 1)
        if len(pdf_slimmed) == 1:
            if pub is not None: pub['footer fail'] = 'X'
            pa_print.tprint('Could not split footer during parsing!')
        else:
            pdf_slimmed = pdf_slimmed[0]
            # pa_print.tprint('Split footer at references')
    else:
        pdf_slimmed = pdf_slimmed[0]
        # pa_print.tprint('Split footer at acknowledgements')

    return pdf_slimmed

def clean_text(doc, user_config=None, miner=False):
    '''Pre-process essential text into word counts (or other models).
    Optional inputs for use in modelling.

    :document from text extraction (miner) or xml extraction (grobid)
    '''
    # print('\nCleaning text...')

    if user_config is not None:
        keywords =  user_config[0]
        ignore_words =  user_config[1]
        merge_words =  user_config[2]
        # selected_years =  user_config[3]

    if miner is True: # no need to trim with grobid text
        doc_trimmed = trim_headfoot(doc)

    else:
        doc_trimmed = doc

    # Check for decoding errors (does not catch all) # ! REPLACE WITH QUALITY_CHECK
    pre_cid = len(doc_trimmed)
    doc_trimmed = re.sub(r'\(cid:[0-9]+\)','', doc_trimmed, re.M) # when font cannot be decoded, (cid:#) is returned, remove these
    post_cid = len(doc_trimmed)
    if pre_cid > 5*post_cid: # if most of content was undecodable, skip
        print("File cannot be decoded well, skipping!")
        return

    # Normalize text and tokenize
    doc_processed = doc_trimmed.lower() # lowercase
    doc_processed = re.sub(r'(?:[^a-zA-Z]+)|(?:\s+)', ' ', doc_processed) # remove non-alpha and line breaks
    words = word_tokenize(doc_processed) # tokenize
    words = [word for word in words if word.isalpha() and len(word) > 3] # alpha only and over 3 chars
    stop_words = STOPWORDS

    # porter = PorterStemmer()
    # processed_words = [porter.stem(word) for word in words] # stem words

    lemmatizer = WordNetLemmatizer() # lemmatizing for semantic relevance
    words = [lemmatizer.lemmatize(word) for word in words] # lemmatize words

    if user_config is not None:
        try: # Remove ignore words from all words
            stop_words = stop_words.union(set(ignore_words)) # custom.csv
        except NameError:
            pass
        try: # Change words that should be merged to first cell in merge group
            for merge_group in merge_words:
                for i, w in enumerate(words):
                    if w in merge_group[1:]:
                        words[i] = merge_group[0]
        except NameError:
            pass

    processed_words = [w for w in words if not w in stop_words] # prune stop words

    return processed_words
