# This file is part of the NIME Proceedings Analyzer (NIME PA)
# Copyright (C) 2021 Jackson Goode, Stefano Fasciani

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

# S. Fasciani, J. Goode, 20 NIMEs: Twenty Years of New Interfaces for Musical
# Expression, in proceedings of 2021 International Conference on New Interfaces
# for Musical Expression, Shanghai, China, 2021.

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


def prep(args):
    # Delete cache
    if args.redo:
        answer = boolify(input('Do you want to delete PDFs as well? (y/N): '))
        if answer:
            shutil.rmtree('./cache')
        else:
            for p in ['text', 'xml', 'bibtex', 'json']:
                shutil.rmtree(f'./cache/{p}')

    # Generate cache folders
    for folder in ['./cache/pdf/', './cache/xml/',
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


def check_grobid(bib_db, overwrite=False):
    ''' Repopulate Grobid files, downloads PDFs if needed

    :bib_db from bibtex file
    '''
    def get_session():
        if not hasattr(thread_local, "session"):
            thread_local.session = requests.Session()
        return thread_local.session

    def download_url(url, dl_path=pdf_src, fn=None):
        if fn is not None:
            pdf_name = fn
        else:
            pdf_name = url.split('/')[-1]

        session = get_session()

        print(f'Downloading {url}...')
        with session.get(url) as r:
            if r.status_code == requests.codes.ok:
                # scan pubpub page for xml file
                if 'pubpub' in url and '.pdf' not in url:
                    pubpub_url = re.search(r"pdf&quot;,&quot;url&quot;:&quot;(.*?.pdf)", r.text).group(1)
                    pub = [pub for pub in bib_db if url in pub['url']][0]
                    fn = f"nime{pub['year']}_{pub['article-number']}.pdf"
                    download_url(pubpub_url, fn=fn)
                    return
                open(dl_path + pdf_name, 'wb').write(r.content)
            else:
                url, title = pub['url'], pub['title']
                print(f'\nFailed to download from {url} the paper: {title}'
                      '\nRun the script again to attempt re-downloading the file.'
                      f'\nIf the problem persists, download the file manually and save it in resources/corrected as {pdf_name}.\n')
                quit()

    # Check for pdfs
    print('Checking PDFs and converting to XML!')
    xmls = os.listdir(xml_src)
    pdfs = os.listdir(pdf_src)

    thread_local = threading.local()

    url_dict = {}
    for pub in bib_db:
        if 'pubpub' in pub['url']:
            url_dict[f"nime{pub['year']}_{pub['article-number']}.pdf"] = pub['url']
        else:
            url_dict[pub['url'].split('/')[-1]] = pub['url']

    # pdfs that aren't downloaded yet
    dl_files = list(set(url_dict.keys()) - set(pdfs))
    dl_urls = [url_dict[f] for f in dl_files]

    # Multithread downloads
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(download_url, dl_urls)

    check_xmls = [pdf.split('.')[0]+'.tei.xml' for pdf in url_dict.keys()]
    bad_xmls = list(set(check_xmls) - set(xmls))

    if len(bad_xmls) > 0:
        print(f'Found {len(bad_xmls)} PDFs unconverted - converting!')
        generate_grobid(overwrite)
    else:
        answer = boolify(input(f'All XMLs exist - convert anyway? (y/N): '))
        if answer:
            generate_grobid(True)


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
