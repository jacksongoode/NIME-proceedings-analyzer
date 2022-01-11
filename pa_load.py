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
# Archive, submitted to 2022 International Conference on New Interfaces for
# Musical Expression, Auckland, New Zealand, 2022.

# Native
import os
import requests
from collections import defaultdict
import zipfile
import urllib
import subprocess
import time
import socket
import signal
import shutil
import concurrent.futures
import threading
import re

# External
from tqdm import tqdm
import orjson
import bibtexparser
import oschmod
from grobid_client.grobid_client import GrobidClient

# Helper
import pa_print
import pa_extract
from pa_utils import doc_check, fill_empty, boolify

# Variables
bibtex_url = 'https://raw.githubusercontent.com/NIME-conference/NIME-bibliography/master/paper_proceedings/nime_papers.bib'
unidomains_url = 'https://raw.githubusercontent.com/Hipo/university-domains-list/master/world_universities_and_domains.json'
unused_cols = ['ID', 'ENTRYTYPE', 'doi', 'annote', 'booktitle', 'editor', 'date', 'date-modified',
               'editor', 'isbn', 'issn', 'month', 'publisher', 'rating', 'series', 'track', 'pages',
               'presentation-video', 'urlsuppl1', 'urlsuppl2', 'urlsuppl3', 'volume']
pdf_src = os.getcwd()+'/cache/pdf/'
xml_src = os.getcwd()+'/cache/xml/'
jats_src = os.getcwd()+'/cache/jats/'


def prep(args):
    # Delete cache
    if args.redo:
        answer = boolify(input('Do you want to delete PDFs as well? (y/N): '))
        if answer:
            shutil.rmtree('./cache')
        else:
            for p in ['text', 'xml', 'bibtex', 'json', 'jats']:
                shutil.rmtree(f'./cache/{p}')

    # Generate cache folders
    for folder in ['./cache/pdf/', './cache/xml/', './cache/jats/',
                   './cache/text/grobid/', './cache/text/miner/',
                   './cache/bibtex/', './cache/json/',
                   './output/', './resources/corrected/']:
        os.makedirs(os.path.dirname(f'{folder}'), exist_ok=True)

    # Copy corrected into pdf
    for f in [f for f in os.listdir('./resources/corrected') if f.endswith('.pdf')]:
        shutil.copy(os.path.join('./resources/corrected', f), './cache/pdf')

    # Config load
    if not os.path.exists('./resources/config.json'):
        with open('./resources/config.json', 'w') as fp:
            config = '''{"grobid_server":"localhost","grobid_port":"8070",
                        "batch_size":1000,"sleep_time":5,"coordinates":["persName",
                        "figure","ref","biblStruct","formula"]}
                    '''
            fp.write(config)

    # Restart log
    if os.path.isfile('./lastrun.log'):
        os.remove('./lastrun.log')


def load_unidomains(path):
    ''' Loads unidomain file from json or downloads if not found

    :path of unisomains.json file
    '''
    if not os.path.isfile(path):  # if not, download
        pa_print.tprint('\nDownloading unidomains database...')
        r = requests.get(unidomains_url, allow_redirects=True)
        open(path, 'wb').write(r.content)

    with open(path, 'rb') as fp:
        unidomains = orjson.loads(fp.read())

    return unidomains


def load_bibtex(path):
    ''' Loads BibTeX file into object or downloads if not found

    :path of BibTeX file
    '''
    if not os.path.isfile(path):  # if not, download
        pa_print.tprint('\nDownloading bibtex database...')
        r = requests.get(bibtex_url, allow_redirects=True)
        open(path, 'wb').write(r.content)

    with open(path) as bib_file:
        parser = bibtexparser.bparser.BibTexParser()
        parser.customization = bibtexparser.customization.convert_to_unicode
        bib_db = bibtexparser.load(bib_file, parser=parser)
        bib_db = bib_db.entries

    return bib_db


def extract_bibtex(bib_db, args):
    print('\nExtracting BibTeX...')
    for index, pub in enumerate(tqdm(bib_db)):
        pub = defaultdict(lambda: [], pub)  # ? needed?
        pa_extract.extract_bib(pub, args)

        for col in unused_cols:
            if col in pub:
                del pub[col]

        bib_db[index] = pub  # reinsert trimmed pub
    return bib_db


def check_xml(bib_db, jats=False, overwrite=False):
    ''' Repopulate Grobid files, downloads PDFs if needed

    :bib_db from bibtex file
    '''
    def get_session():
        if not hasattr(thread_local, "session"):
            thread_local.session = requests.Session()
        return thread_local.session

    def download_url(url, fn, dl_path):
        session = get_session()

        try:
            with session.get(url) as r:
                print(f'Downloading {url}...')
                if r.status_code == requests.codes.ok:
                    # Redirect if PubPub url
                    if 'pubpub' in url and '.xml' not in url:
                        url = re.search(r"jats&quot;,&quot;url&quot;:&quot;(.*?.xml)", r.text).group(1)
                        r = session.get(url)
                    open(dl_path + fn, 'wb').write(r.content)
                    time.sleep(0.25) # delay querying resources
                else:
                    url, title = pub['url'], pub['title']
                    print(f'\nFailed to download from {url} the paper: {title}'
                        '\nRun the script again to attempt re-downloading the file.'
                        f'\nIf the problem persists, download the file manually and save it in resources/corrected as {fn}.\n')
                    quit()
        except Exception as e:
            print("Error downloading: ", e)

    def multithread_dls(files, f_dict, dl_path):
        # Download XML and PDFs that don't exist yet
        missing_files = set(f_dict.keys()) - set(files)
        f_dict = {k:v for k, v in f_dict.items() if k in missing_files}

        # Multithread downloads - with urls (values) and fn's (keys)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(download_url, f_dict.values(), f_dict.keys(), [dl_path]*len(f_dict))

    xmls = os.listdir(xml_src)
    thread_local = threading.local()

    if jats:
        print('\nChecking for missing PubPub XMLs!')
        jats = os.listdir(jats_src)
        jats_dict = {}

        for pub in bib_db:
            jats_dict[f"nime{pub['year']}_{pub['article-number']}.xml"] = pub['url']

        multithread_dls(jats, jats_dict, jats_src)

        missing_jats = list(set(jats_dict.keys()) - set(xmls))

        if len(missing_jats) > 0:
            print(f'Found {len(missing_jats)} PubPub XMLs unconverted - converting!')
            generate_teis(missing_jats)
    
    else:
        print('\nChecking for missing PDFs!')
        pdfs = os.listdir(pdf_src)
        pdf_dict = {}

        for pub in bib_db:
            pdf_dict[pub['url'].split('/')[-1]] = pub['url']
        
        multithread_dls(pdfs, pdf_dict, pdf_src)
        
        check_xmls = [pdf.split('.')[0]+'.tei.xml' for pdf in pdf_dict.keys()]
        missing_xmls = list(set(check_xmls) - set(xmls))

        if len(missing_xmls) > 0:
            print(f'Found {len(missing_xmls)} PDFs unconverted - converting!')
            generate_grobid(overwrite)
        else:
            answer = boolify(input(f'All XMLs exist - convert anyway? (y/N): '))
            if answer:
                generate_grobid(True)


def generate_teis(missing_jats):
    # Put xmls in a temp dur for batch conversion
    temp_dir = os.getcwd()+'/cache/temp_jats/'
    for f in missing_jats:
        os.renames(jats_src+f, temp_dir+f)
    try:
        print('\nConverting XMLs from JAR to TEI!')
        oschmod.set_mode('./resources/Pub2TEI/Samples/saxon9he.jar', '+x')
        xslt_args = ['--parserFeature?uri=http%3A//apache.org/xml/features/nonvalidating/load-external-dtd:false',
                    '-dtd:off', '-a:off', '-expand:off',
                    '-xsl:./Stylesheets/Publishers.xsl',
                    f'-s:{temp_dir}', 
                    f'-o:{xml_src}']
        subprocess.run(['java', '-jar', './Samples/saxon9he.jar', *xslt_args], cwd=f'./resources/Pub2TEI')
    except Exception as e:
        print('An error occured: ', e)
        quit()

    # Return xmls to jar dir
    for f in missing_jats:
        os.renames(temp_dir+f, jats_src+f)


def generate_grobid(overwrite=False):
    ''' Convert a pdf to a .tei.xml file via Grobid

    '''
    base = 'https://github.com/kermitt2/grobid/'
    # get latest Grobid release
    version = requests.get(base+'releases/latest').url.split('/')[-1]

    if not os.path.exists(f'./cache/grobid-{version}'):
        print('\nInstalling Grobid!')
        try:
            print('Downloading and extracting...')
            zip_path, _ = urllib.request.urlretrieve(
                f'{base}archive/refs/tags/{version}.zip')
            with zipfile.ZipFile(zip_path, 'r') as f:
                f.extractall('./cache')

            print('Installing...')
            oschmod.set_mode(f'./cache/grobid-{version}/gradlew', '+x')
            subprocess.run(f'cd ./cache/grobid-{version} '
                           '&& ./gradlew clean install', shell=True)
            exec_dir = f'./cache/grobid-{version}/grobid-home/'
            for folder in [exec_dir+'pdf2xml', exec_dir+'pdfalto']:
                for root, _, files in os.walk(folder):
                    for f in files:
                        oschmod.set_mode(os.path.join(root, f), '+x')

        except Exception as e:
            print(e)
            print('\nFailed to install Grobid!')

    print('\nConverting PDFs to XMLs via Grobid - this may take some time...')

    # Kill untracked server if exists
    subprocess.run(['./gradlew', '--stop'], cwd=f'./cache/grobid-{version}', stderr=subprocess.DEVNULL)

    p = subprocess.Popen(
        ['./gradlew', 'run'], cwd=f'./cache/grobid-{version}', stdout=subprocess.DEVNULL)
    for _ in tqdm(range(20), desc='Initiating Grobid server'):
        time.sleep(1)  # wait for Grodid to run, might need to be longer

    if overwrite:
        shutil.rmtree('./cache/xml')

    client = GrobidClient(config_path='./resources/config.json')
    client.process('processFulltextDocument', pdf_src, tei_coordinates=False, output=xml_src, force=overwrite)
    p.terminate()
