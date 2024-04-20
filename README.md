# [NIME](https://www.nime.org/) Proceedings Analyzer

The NIME Proceedings Analyzer (PA) is a tool written in python to perform a bibliometric analysis of the New Interfaces for Musical Expression (NIME) proceedings archive.

The tool is includes four scripts:

1. [pa.py](pa.py) - Generates a rich database from extracted meta-information associated with all [papers published at NIME](https://github.com/NIME-conference/NIME-bibliography/blob/master/paper_proceedings/nime_papers.bib). The database is saved in the file _./output/export.csv_. It also generates plain body-text files associated with all papers inside the _./cache/_ folder.

2. [analysis_meta.py](analysis_meta.py) - Analyzes the metadata stored in _./output/export.csv_. and produces a pair of .txt and .xlsx files in _./output/_ with statistics related to papers, authorship, affiliation, travel.

3. [analysis_topic.py](analysis_topic.py) - Analyzes keywords and topics in the titles and body text of the papers, generates titles and body-text wordclouds, and computes a visualization of topics modeled with the Latent Dirichlet Allocation (LDA) algorithm. Produced files are saved in _./output/_.

4. [analysis_search.py](analysis_search.py) - Searches specific keywords through the papers and it produces a graph with the search terms over the years in a .xlsx file saved in _./output/_.

5. [analysis_citations.py](analysis_citations.py) - Analyzes the references and citation data stored in _./output/export.csv_. and produces a pair of .txt and .xlsx files in _./output/_ with statistics related to papers citing and cited in NIME.


## Description & Usage

### Requirements

The NIME PA requires Python 3.11, Java JDK 1.11 and an active Internet connection.

Install required packages:

```sh
pip install -r requirements.txt
```

Run the scripts with any additional flags (see below):

```sh
python pa.py
python analysis_meta.py
python analysis_topic.py
python analysis_search.py
python analysis_refcits.py
```

Note: location-based analyses uses data from [OpenCage Data](https://opencagedata.com/) for which you must provide an API key (currently free registration provides a key for 2500 requests per day).

Note: bibliometric-based analyses uses data from [Semantic Scholar](https://www.semanticscholar.org/) for which you may provide an API key to access the service at a faster rate.

Note: For Macbooks based on arm, a the library located at `/NIME-proceedings-analyzer/cache/grobid-{version}/grobid-home/lib/mac-64/libwapiti.dylib` may not work properly with the device. In this case, a pre-built lib has been made available within `resources/misc/libwapiti.dylib`. This can be overwrite the installed lib if needed.

## pa.py

This script produces a database which includes an entry for each published NIME paper. For each paper the database includes:

- information extracted from the [NIME BibTex Archive](https://github.com/NIME-conference/NIME-bibliography)
- additional information extracted from the PDF file of the papers using [Grobid](https://github.com/kermitt2/grobid)
- location and affiliation of the authors, extracted using a combination methods and data from [Open Cage Data](https://opencagedata.com/) that minimize estimation errors
- gender of the authors estimated using a [binary](https://github.com/parthmaul/onomancer) and [non-binary method](https://github.com/lead-ratings/gender-guesser)
- number of citations received by the paper and key citations extracted from [Semantic Scholar](https://www.semanticscholar.org/)
- estimated distance and carbon footprint for authors traveling to the conference.

All the materials above are automatically downloaded and extracted as publicly available resources and stored in the local _./cache/_ folder. Only the conference locations are provided in the file _./resources/conferences.csv_, which contains information up to and including year 2020. Additionally, the script produces a plain text files of the body for all papers which is stored in _./cache/text/_.

The script accepts the following optional arguments:

- **-h, --help** show this help message and exit
- **-v, --verbose** prints out operations
- **-c, --citations** bypass cache to retrieve new citations
- **-g, --grobid** forces repopulation of Grobid files
- **-r, --redo** deletes cache
- **-n, --nime** uses NIME specific corrections
- **-p, --pdf** use manually downloaded pdf for PubPub publications
- **-ock OCKEY, --ockey OCKEY** OpenCage Geocoding API key
- **-ssk SSKEY, --sskey SSKEY** Semantic Scholar API key
- **-s SLEEP, --sleep SLEEP** sleep time (sec) between Semantic Scholar API requests

The first execution of the script will take a significant amount of time, approximately 12 hours.
The most time consuming operations are: downloading of PDF files associated with the papers, generating xml files associated with the papers and stored in _./cache/xml/_ through Grobid, and querying Semantic Scholar (due to their public API limit).

Depending on the arguments, the script may interactively prompt "Yes"/"No" questions to the user in the initial phases of the execution.

**-v**: This argument prints details of the script's progress. Thanks to the cache, if the script encounters a temporary error (e.g. fail to download a file) or if it gets intentionally interrupted, data computed/downloaded in the previous run will not be lost. When restarted, the script will quickly progress to the point in which it was interrupted.

**-c**: Citations associated with papers changes very frequently and this argument forces the script to bypass the citation info stored in the cache file and retrieve new ones from Semantic Scholar. The updated citation number is then stored in the cache.

**-g**: This argument forces the script to regenerate the xml files associated with the papers using Grobid. This may be suitable when a new version of Grobid is released. The script downloads and uses the latest release of Grobid. You can check the used version from the associated cache folder.

**-r**: This argument deletes all cached files to make a clean start.

**-n**: This argument enables a few manual corrections of author names and gender specific to NIME authors. Despite an effort to make the tool as generic and robust as possible, there are still a few exceptions, often due to inconsistent recording of data. Their handling is managed by the portions of the script which are executed only if this argument is passed to the script.

**-p**: This argument enables to use PDF instead of XML for papers published in PubPub. Analyzing PDF may be preferred as PubPub keeps changing frequently and this tool is not updated at the same rate. However, automatic download of PDF papers from PubPub is not possible. If selecting this option the collection of 2021 and 2022 PubPub papers must be manually downloaded, renamed with the associated ID found in the [NIME BibTex File](http://nime-conference.github.io/NIME-bibliography/nime_papers.bib) (e.g. NIME22_16.pdf) and placed in the folder _./resources/pubpub/_ . Alternatively the same collection of PubPub PDF files (with proper renaming and correction of malformed files) can be downloaded [here](https://drive.google.com/uc?export=download&id=1i2ulr9XmHm3hlHuXCEPOFQf2JfLMXodg).

**-ock OCKEY**: This argument allows to specify an [OpenCage Geocoding API Key](https://opencagedata.com/api) which is necessary to request location-related data. A free key allows only 2500 requests per day.

This argument allows to specify a [Semantic Scholar API Key](https://www.semanticscholar.org/product/api#api-key) to request citations and list of reference data at faster rate (default is 5000 requests per 5 minutes).

**-ssk SSKEY**: This argument allows to specify a [Semantic Scholar API Key](https://www.semanticscholar.org/product/api#api-key) to request citations and list of reference data at faster rate (default is 5000 requests per 5 minutes).

**-s SLEEP**: This argument allows to specify a custom sleep time (in seconds) between consecutive Semantic Scholar API request, which is needed when using a Semantic Scholar API Key allowing a higher request-rate (default sleep is 0.06 sec).


### analysis_meta.py

This script analyzes the metadata stored in _./output/export.csv_. and produces statistics related to 1) papers, 2) authorship, 3) affiliation, 4) travel. This script requires the data generated by the pa.py script.

The script accepts the following optional arguments:

- **-h, --help** show this help message and exit
- **-v, --verbose** prints out operations
- **-n, --nime** uses NIME based corrections

**-v**: This argument prints details of the script's progress.

**-n**: This argument forces a few correction on author names and gender specific to NIME authors. In the current version this argument has no effect.

The analysis can be restricted to specific years through the [custom.csv](#custom.csv) file in the _./resources/_ folder.

The script interactively prompt "Yes"/"No" questions for computing the statistics associated with the four above-mentioned categories.

The statistics computed by the script are stored in the following files:

- _./output/papers.txt_
- _./output/papers.xlsx_
- _./output/authors.txt_
- _./output/authors.xlsx_
- _./output/affiliations.txt_
- _./output/affiliations.xlsx_
- _./output/travel.txt_
- _./output/travel.xlsx_

Overall statistics and are included in the .txt files. Detailed statistic per year, paper, author, institution, country, continent, etc., are included in the .xlsx files.

Figures related to page count are reported only for papers before 2021. Thereafter, with the new publication format (PupPub), paper length is measured only in terms of word count.

In the .xlsx files, sheet names are limited to 31 characters and the following abbreviations are used:

```text
avg. = average
num. = number
cit. = citations
pr. = per
yr. = year
norm. = normalized
auth. = author
pub. = publication
dist. = distance
distr. = distribution
footp. = footprint
part. = participant
cont. = continent
count. = country
instit. = institute
\> = more than
% = percentage
\# = number of
```

## analysis_topic.py

This script analyzes topics in the titles and body text of the papers, and it produces 1) statistical and trends on keywords, 2) titles and body-text wordclouds, and 3) a visualization of topics modeled with the Latent Dirichlet Allocation (LDA) algorithm. Produced files are saved in _./output/topics.xlsx_. This script requires the data generated by the pa.py script.

The script accepts the following optional arguments:

- **-h, --help** show this help message and exit
- **-v, --verbose** prints out operations
- **-n, --nime** uses NIME based corrections

**-v**: This argument prints details of the script's progress.

**-n**: This argument forces a few correction on author names and gender specific to NIME authors. In the current version this argument has no effect.

The analysis can be customized through the _custom.csv_ file in the _./resources/_ folder.

The script interactively prompt "Yes"/"No" questions for computing the data associated with the three above-mentioned categories.

In respect to generating LDA model, a user can choose how many topics the algorithm will attempt to categorize from the relative frequencies of words in the corpus. This will require compiling all text from each paper into a large dictionary and corpus. Both the model and the dict. and corpus are saved in the _./cache/lda_ folder Thus, four options are available upon running to create a new model, rebuild dictionary and corpus, do both, or load a prebuilt model.

The script produces the following output files:

- _./output/topics.xlsx_
- _./output/topic_occurrence.png_
- _./output/wordcloud_bodies.png_
- _./output/wordcloud_titles.png_
- _./output/lda.html_

## analysis_refcit.py

This script analyzes the metadata stored in _./output/export.csv_. and produces statistics related to references (i.e. works cited in NIME papers) and to citations (i.e. works citing NIME papers). This script requires the data generated by the pa.py script.

The script accepts the following optional arguments:

- **-h, --help** show this help message and exit
- **-v, --verbose** prints out operations
- **-n, --nime** uses NIME based corrections

**-v**: This argument prints details of the script's progress.

**-n**: This argument forces a few correction on author names and gender specific to NIME authors. In the current version this argument has no effect.

The analysis can be restricted to specific years through the [custom.csv](#custom.csv) file in the _./resources/_ folder.

The script interactively prompt "Yes"/"No" questions for computing the statistics associated with the four above-mentioned categories.

The statistics computed by the script are stored in the following files:

- _./output/refcit.txt_
- _./output/refcit.xlsx_

## analysis_search.py

This script provides a quick method of searching through the documents with keywords specified in the _./resources/custom.csv_. It produces a graph with the search terms listed over the specified year range.

The script produces the following output files:

- _./output/keyword_occurrence.png_
- _./output/keyword_occurrence.xlsx_

### custom.csv

Through this file, located in the _./resources/_ folder, it is possible to customize the metadata and topic analysis. The following entries are allowed:

- **years**: restrict the analysis to specific years (single cell), or to a a specific range (two adjacent cells). This entry can be repeated across multiple rows for incongruent years. This works with _analysis_meta.py_, _analysis_topic.py_, analysis_refcit.py, and _analysis_search.py_.

- **keywords**: specify words (one in each cell) that can be queried for occurrence frequency using _analysis_search.py_.

- **ignore**: specify words that will be ignored from word counts tallies. This works only with _analysis_topic.py_.

- **merge**: specify words that should be merged together, where the left-most cell will be the word that other words (that follow from the right) will be changed to. This works only with _analysis_topic.py_.

An example of the analysis customization file is available [here](resources/custom_ex.csv).

## Troubleshooting

The following tips may help to troubleshoot the execution of pa.py:

1. A temporary log file _lastrun.log_ is generated in the root folder with the details of all operations during the last run of each script. This file is regenerated on each run of each script. It can be used to inspect the results of a last run or if errors had occurred during its execution.

2. If you encounter an error that interrupts pa.py, restart the execution with the same arguments (with exception of those deleting caches and forcing the regeneration of xml files). The script is able to quickly resume from the point in which it has been interrupted, and if the nature of the error was temporary (e.g. a download failure due to network problems) the script is should be able to continue the process.

3. If facing consistent problems with one or more specific papers, such as download failing, or failing to extract data from PDF files because corrupted or badly encoded (i.e. associated word count equal to 0 in export.csv), the user can manually download the paper from another source, name it as specified in the [NIME BibTex File](http://nime-conference.github.io/NIME-bibliography/nime_papers.bib), and place it in the folder _./resources/corrected/_. It is also recommended to remove the associated files with a similar file name that may have been created in _./cache/xml/_, _./cache/text/miner/_, and _./cache/text/grobid/_.

4. When badly encoded papers are not available elsewhere, it is possible to recover them using [OCRmyPDF](https://github.com/jbarlow83/OCRmyPDF), which is a tool to add an OCR text layer to scanned PDF files, but it also works well to replace the badly encoded original text. Often OCRmyPDF significantly increase file size, but files can be further compressed using a third party tool or using the same script and adding compression options at line 16. A limitation of OCRmyPDF is that the generated text layer also includes text found in images. The folder _./resources/corrected/_ in the releases includes all papers we fixed or sourced elsewhere due to download or encoding problems. Alternatively the same collection of fixed PDF files can be downloaded [here](https://drive.google.com/uc?export=download&id=1MYDYltsSlpDPnRF0wN2-BZnQ99-NNRDN).

5. At times, the download of the PDF file may fail but a zero-bytes file is still generated in the folder _./cache/pdf/_. As a consequence, incomplete data related to the paper will be stored in export.csv. After a complete execution of pa.py it is recommended to look for zero-bytes PDF in _./cache/pdf/_, remove them and the associated files created in _./cache/xml/_, _./cache/text/miner/_, and _./cache/text/grobid/_. Then restart pa.py with the same arguments (with exception of those deleting caches and forcing the regeneration of xml files), the new export.csv file with complete information will be generated in a fairly short amount of time.

6. To speed up the download of the PDF files, the analyzer uses multiple threads downloading files in parallel. At times this may fail either generating a long sequence of download error messages, or downloading corrupted PDF files (that will determine an error later on in the analysis process). To avoid this possible problem, set _max_workers=1_ at line 195 of _pa_load.py_.

7. If using a free [OpenCage Geocoding API Key](https://opencagedata.com/api), the limit of 2500 requests per day is not sufficient to complete the execution of [pa.py](pa.py) when starting from empty cache. Moreover, [pa.py](pa.py) does not keep track of the number of requests and at some point you may start to get warning message with exception messages from OpenCageGeocode. Currently we estimate that approximately 3000 requests are necessary. Location data requested from OpenCage is stored in _./cache/json/location_cache.json_. Therefore, when starting from empty cache using a free API key, you should interrupt [pa.py](pa.py) once it pass 50% and then restart after 24 hours. Once the cache file _location_cache.json_ is populated, the request limit no longer affects the execution of [pa.py](pa.py).

## Resources

The extracted data from 2001 to 2020 is presented in:  
S. Fasciani, J. Goode, [20 NIMEs: Twenty Years of New Interfaces for Musical Expression](https://nime.pubpub.org/pub/20nimes/), in proceedings of 2021 International Conference on New Interfaces for Musical Expression, Shanghai, China, 2021.

The data presented in the paper has been manually polished and arranged in a [spreadsheet](https://docs.google.com/spreadsheets/d/134zxeEhhXp3o7G_S1oDVjDymPuj2J3Wj3ftEAdOEo8g/edit?usp=drive_link), which includes a collection of plots and data visualizations.

```text
@inproceedings{NIME21_1,
    address = {Shanghai, China},
    articleno = {1},
    author = {Fasciani, Stefano and Goode, Jackson},
    booktitle = {Proceedings of the International Conference on New Interfaces for Musical Expression},
    doi = {10.21428/92fbeb44.b368bcd5},
    issn = {2220-4806},
    title = {20 NIMEs: Twenty Years of New Interfaces for Musical Expression},
    url = {https://nime.pubpub.org/pub/20nimes},
    year = {2021}
}
```

The extracted data related to references and citations from 2001 to 2023 is presented in:  
S. Fasciani [Bibliometric Analysis of NIME References and Citations](http://nime.org/proceedings/2023/nime2024_15.pdf), in proceedings of 2024 International Conference on New Interfaces for Musical Expression, Utrecht, Netherlands, 2024.

The data presented in the paper has been manually polished and arranged in a [spreadsheet](https://docs.google.com/spreadsheets/d/1swmSw3Uwja9N64t-qgkzpupaTqIZyD4bjftbgPMzmLk/edit?usp=drive_link), which includes a collection of plots and data visualizations.


```text
@article{nime2024_15,
    address = {Utrecht, Netherlands},
    articleno = {15},
    author = {Fasciani, Stefano},
    booktitle = {Proceedings of the International Conference on New Interfaces for Musical Expression},
    doi = {},
    issn = {2220-4806},
    title = {Bibliometric Analysis of NIME References and Citations},
    url = {http://nime.org/proceedings/2024/nime2024_15.pdf},
    year = {2024}
}
```

In the release section, there are versions of of this repository after the the execution of all scripts on a specific date. This include also all output and cache files except for the PDF associated with the papers (due to file size reason). Releases can be used run the meta and topic analysis without waiting for the pa.py script to generate the necessary files, or to force pa.py to update only selected outputs through the available arguments.

## License

All code in this repository is licensed under [GNU GPL 3.0](https://www.gnu.org/licenses/gpl-3.0.html).

```text
NIME Proceedings Analyzer (NIME PA)
Copyright (C) 2024 Jackson Goode, Stefano Fasciani

The NIME PA is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

The NIME PA is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

If you use the NIME Proceedings Analyzer or any part of it in any program or
publication, please acknowledge its authors by adding a reference to:

@inproceedings{NIME22_16,
    address = {Auckland, New Zealand},
    articleno = {16},
    author = {Goode, Jackson and Fasciani, Stefano},
    booktitle = {Proceedings of the International Conference on New Interfaces for Musical Expression},
    doi = {10.21428/92fbeb44.58efca21},
    issn = {2220-4806},
    pdf = {13.pdf},
    title = {A Toolkit for the Analysis of the {NIME} Proceedings Archive},
    url = {https://doi.org/10.21428%2F92fbeb44.58efca21},
    year = {2022}
}
```