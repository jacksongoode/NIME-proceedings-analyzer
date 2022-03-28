# [NIME](https://www.nime.org/) Proceedings Analyzer

The NIME Proceedings Analyzer (PA) is a tool written in python to perform a bibliographic analysis of the New Interfaces for Musical Expression (NIME) proceedings archive.

The tool is includes four scripts:

1. [pa.py](pa.py) - Generates a rich database from extracted meta-information associated with all [papers published at NIME](https://github.com/NIME-conference/NIME-bibliography/blob/master/paper_proceedings/nime_papers.bib). The database is saved in the file *./output/export.csv*. It also generates plain body-text files associated with all papers inside the *./cache/* folder.

2. [analysis_meta.py](analysis_meta.py) - Analyzes the metadata stored in *./output/export.csv*. and produces a pair of .txt and .xlsx files in *./output/* with statistics related to papers, authorship, affiliation, travel.

3. [analysis_topic.py](analysis_topic.py) - Analyzes keywords and topics in the titles and body text of the papers, generates titles and body-text wordclouds, and computes a visualization of topics modeled with the Latent Dirichlet Allocation (LDA) algorithm. Produced files are saved in *./output/*.

4. [analysis_search.py](analysis_search.py) - Searches specific keywords through the papers and it produces a graph with the search terms over the years in a .xlsx file saved in *./output/*.

## Description & Usage

### Requirements

The NIME PA requires Python 3.7 (recommended) or higher.

Install required packages:
```
pip install -r requirements.txt
```

Run the scripts with any additional flags (see below):
```
python pa.py
python analysis_meta.py
python analysis_topic.py
python analysis_search.py
```

## pa.py

This script produces a database which includes an entry for each published NIME paper. For each paper the database includes:
- information extracted from the [NIME BibTex Archive](https://github.com/NIME-conference/NIME-bibliography/blob/master/paper_proceedings/nime_papers.bib)
- additional information extracted from the PDF file of the papers using [Grobid](https://github.com/kermitt2/grobid)
- location and affiliation of the authors, extracted using a combination methods that minimizes errors
- gender of the authors estimated using a [binary](https://github.com/parthmaul/onomancer) and [non-binary method](https://github.com/lead-ratings/gender-guesser)
- number of citations received by the paper and key citations extracted from [Semantic Scholar](https://www.semanticscholar.org/)
- estimated distance and carbon footprint for authors traveling to the conference.

All the materials above are automatically downloaded and extracted as publicly available resources and stored in the local *./cache/* folder. Only the conference locations are provided in the file *./resources/conferences.csv*, which contains information up to and including year 2020. Additionally, the script produces a plain text files of the body for all papers which is stored in *./cache/text/*.

The script accepts the following optional arguments:
-  **-h, --help**       show this help message and exit
-  **-v, --verbose**    prints out operations
-  **-c, --citations**  bypass cache to retrieve new citations
-  **-g, --grobid**     forces repopulation of Grobid files
-  **-r, --redo**       deletes cache
-  **-n, --nime**       uses NIME specific corrections

The first execution of the script will take a significant amount of time, approximately 12 hours.
The most time consuming operations are: downloading of PDF files associated with the papers, generating xml files associated with the papers and stored in *./cache/xml/* through Grobid, and querying Semantic Scholar (due to their public API limit).

Depending on the arguments, the script may interactively prompt "Yes"/"No" questions to the user in the initial phases of the execution.

**-v**: This argument prints details of the script's progress. Thanks to the cache, if the script encounters a temporary error (e.g. fail to download a file) or if it gets intentionally interrupted, data computed/downloaded in the previous run will not be lost. When restarted, the script will quickly progress to the point in which it was interrupted.

**-c**: Citations associated with papers changes very frequently and this argument forces the script to bypass the citation info stored in the cache file and retrieve new ones from Semantic Scholar. The updated citation number is then stored in the cache.

**-g**: This argument forces the script to regenerate the xml files associated with the papers using Grobid. This may be suitable when a new version of Grobid is released. The script downloads and uses the latest release of Grobid. You can check the used version from the associated cache folder.

**-r**: This argument deletes all cached files to make a clean start.

**-n**: This argument enables a few manual corrections of author names and gender specific to NIME authors. Despite an effort to make the tool as generic and robust as possible, there are still a few exceptions, often due to inconsistent recording of data. Their handling is managed by the portions of the script which are executed only if this argument is passed to the script.

### analysis_meta.py

If facing consistent problems with one or more specific papers (such as download failing, or failing to extract data to PDF file because corrupted or badly encoded), the user can manually download the paper from another source, name it as specified in the [NIME BibTex Archive](https://github.com/NIME-conference/NIME-bibliography/blob/master/paper_proceedings/nime_papers.bib), and place it in the folder *./resources/corrected/*.

This script analyzes the metadata stored in *./output/export.csv*. and produces statistics related to 1) papers, 2) authorship, 3) affiliation, 4) travel. This script requires the data generated by the pa.py script.

The script accepts the following optional arguments:
-  **-h, --help**       show this help message and exit
-  **-v, --verbose**    prints out operations
-  **-n, --nime**       uses NIME based corrections

**-v**: This argument prints details of the script's progress.

**-n**: This argument forces a few correction on author names and gender specific to NIME authors. In the current version this argument has no effect.

The analysis can be restricted to specific years through the [custom.csv](#custom.csv) file in the *./resources/* folder.

The script interactively prompt "Yes"/"No" questions for computing the statistics associated with the four above-mentioned categories.

The statistics computed by the script are stored in the following files:
- *./output/papers.txt*
- *./output/papers.xlsx*
- *./output/authors.txt*
- *./output/authors.xlsx*
- *./output/affiliations.txt*
- *./output/affiliations.xlsx*
- *./output/travel.txt*
- *./output/travel.xlsx*

Overall statistics and are included in the .txt files. Detailed statistic per year, paper, author, institution, country, continent, etc., are included in the .xlsx files.

Figures related to page count are reported only for papers before 2021. Thereafter, with the new publication format (PupPub), paper length is measured only in terms of word count.

In the .xlsx files, sheet names are limited to 31 characters and the following abbreviations are used:
```
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

This script analyzes topics in the titles and body text of the papers, and it produces 1) statistical and trends on keywords, 2) titles and body-text wordclouds, and 3) a visualization of topics modeled with the Latent Dirichlet Allocation (LDA) algorithm. Produced files are saved in *./output/topics.xlsx*. This script requires the data generated by the pa.py script.

The script accepts the following optional arguments:
-  **-h, --help**       show this help message and exit
-  **-v, --verbose**    prints out operations
-  **-n, --nime**       uses NIME based corrections

**-v**: This argument prints details of the script's progress.

**-n**: This argument forces a few correction on author names and gender specific to NIME authors. In the current version this argument has no effect.

The analysis can be highly customized through the *custom.csv* file in the *./resources/* folder.

The script interactively prompt "Yes"/"No" questions for computing the data associated with the three above-mentioned categories.

In respect to generating LDA model, a user can choose how many topics the algorithm will attempt to categorize from the relative frequencies of words in the corpus. This will require compiling all text from each paper into a large dictionary and corpus. Both the model and the dict. and corpus are saved in the *./cache/lda* folder Thus, four options are available upon running to create a new model, rebuild dictionary and corpus, do both, or load a prebuilt model.

The script produces the following output files:
- *./output/topics.xlsx*
- *./output/topic_occurrence.png*
- *./output/wordcloud_bodies.png*
- *./output/wordcloud_titles.png*
- *./output/lda.html*

## analysis_search.py

This script provides a quick method of searching through the documents with keywords specified in the *./resources/custom.csv*. It produces a graph with the search terms listed over the specified year range.

The script produces the following output files:
- *./output/keyword_occurrence.png*
- *./output/keyword_occurrence.xlsx*

### custom.csv

Through this file, located in the *./resources/* folder, it is possible to customize the metadata and topic analysis. The following entries are allowed:

- **years**: restrict the analysis to specific years (single cell), or to a a specific range (two adjacent cells). This entry can be repeated across multiple rows for incongruent years. This works with *analysis_meta.py*, *analysis_topic.py*, and *analysis_search.py*.

- **keywords**: specify words (one in each cell) that can be queried for occurrence frequency using *analysis_search.py*.

- **ignore**: specify words that will be ignored from word counts tallies. This works only with *analysis_topic.py*.

- **merge**: specify words that should be merged together, where the left-most cell will be the word that other words (that follow from the right) will be changed to. This works only with *analysis_topic.py*.

An example of the analysis customization file is available [here](resources/custom_ex.csv).

## Troubleshooting

The following tips may help to triubleshoot the execution of pa.py:

1. A temporary log file *lastrun.log* is generated in the root folder with the details of all operations during the last run of each script. This file is regenerated on each run of each script. It can be used to inspect the results of a last run or if errors had occurred during its execution.

2. If you encounter an error that interrupts pa.py, restart the execution with the same arguments (with exception of those deleting caches and forcing the regeneration of xml files). The script is able to quickly resume from the point in which it has been interrupted, and if the nature of the error was temporary (e.g. a download failure due to network problems) the script is should be able to continue the process.

3. If facing consistent problems with one or more specific papers, such as download failing, or failing to extract data from PDF files because corrupted or badly encoded (i.e. associated word count equal to 0 in export.csv), the user can manually download the paper from another source, name it as specified in the [NIME BibTex Archive](https://github.com/NIME-conference/NIME-bibliography/blob/master/paper_proceedings/nime_papers.bib), and place it in the folder *./resources/corrected/*. It is also recommended to remove the associated files with a similar file name that may have been created in *./cache/xml/*, *./cache/text/miner/*, and *./cache/text/grobid/*.

4. When badly encoded papers are not available elsewhere, it is possible to recover them using [OCRmyPDF](https://github.com/jbarlow83/OCRmyPDF), which is a tool to add an OCR text layer to scanned PDF files, but it also works well to replace the badly encoded original text. Often OCRmyPDF significantly increase file size, but files can be further compressed using a third party tool or using the same script and adding compression options at line 16. A limitation of OCRmyPDF is that the generated text layer also includes text found in images. The folder *./resources/corrected/* in the releases includes all papers we fixed or sourced elsewhere due to download or encoding problems.

5. At times, the download of the PDF file may fail but a zero-bytes file is still generated in the folder *./cache/pdf/*. As a consequence, incomplete data related to the paper will be stored in export.csv. After a complete execution of pa.py it is recommended to look for zero-bytes PDF in *./cache/pdf/*, remove them and the associated files created in *./cache/xml/*, *./cache/text/miner/*, and *./cache/text/grobid/*. Then restart pa.py with the same arguments (with exception of those deleting caches and forcing the regeneration of xml files), the new export.csv file with complete information will be generated in a fairly short amount of time.

## Resources

The extracted data from 2001 to 2020 is presented in:  
S. Fasciani, J. Goode, [20 NIMEs: Twenty Years of New Interfaces for Musical Expression](https://nime.pubpub.org/pub/20nimes/), in proceedings of 2021 International Conference on New Interfaces for Musical Expression, Shanghai, China, 2021.

The data presented in the paper has been further manually polished and arranged in a [spreadsheet](https://docs.google.com/spreadsheets/d/134zxeEhhXp3o7G_S1oDVjDymPuj2J3Wj3ftEAdOEo8g/edit?usp=sharing), which includes a large collection of plots and data visualizations.

In the release section, there are versions of of this repository after the the execution of all scripts on a specific date. This include also all output and cache files except for the PDF associated with the papers (due to file size reason). Releases can be used run the meta and topic analysis without waiting for the pa.py script to generate the necessary files, or to force pa.py to update only selected outputs through the available arguments.

## License

All code in this repository is licensed under [GNU GPL 3.0](https://www.gnu.org/licenses/gpl-3.0.html).

```
NIME Proceedings Analyzer (NIME PA)
Copyright (C) 2022 Jackson Goode, Stefano Fasciani

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

J. Goode, S. Fasciani, A Toolkit for the Analysis of the NIME Proceedings
Archive, in 2022 International Conference on New Interfaces for
Musical Expression, Auckland, New Zealand, 2022.
```
