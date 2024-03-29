# Data Collection
Data collection is broken down into three steps:
1. Scape PDFs from the CERN Document Server (CDS)
1. Convert PDFs to markdown (NOUGAT) and collect metadata
1. Parse markdown and metadata and add to vector database

## Scape PDFs from CDS



# Find My Plot - Mention Extractor

## Overview
The Mention Extractor script (`get_mentions.py`) is part of the "Find My Plot" project, which aims to make it easier to access figures and tables mentioned in scientific papers. This script automates the extraction of figure and table references from LaTeX files of papers, alongside metadata from accompanying text files. The extracted data includes the mentions of figures and tables, their captions, and links to the papers, organized in a structured JSON format for easy access and analysis.

## Features
- **Automated Extraction**: Processes directories of scientific papers, extracting mentions of figures and tables.
- **Structured Output**: Generates a JSON file containing organized details about figures and tables, including references, captions, and paper
- **Logging**: Detailed logging of processing steps and errors to a file (`log_mentions.txt`), aiding in troubleshooting and ensuring data integrity.

## Usage

To use the Mention Extractor script, you need to specify the input directory containing the papers' data and the output directory for the JSON file.

```
python get_mentions.py [dataDir] [outputDir]
```

- `dataDir`: The directory path containing subdirectories for each paper, which should include LaTeX files and metadata files.
- `outputDir`: The directory path where the generated JSON file will be saved. If it does not exist, the script will attempt to create it.

### Example

```
python get_mentions.py ./path/to/papers ./path/to/output

```


This command processes all papers located in `./path/to/papers`, generating a JSON file in `./path/to/output`.

## Installation

No specific installation steps are required beyond having Python 3.x installed on your system. However, ensure all required Python packages mentioned at the top of the `get_mentions.py` script are installed. You can install any missing packages using pip:

```
pip install -r requirements.txt

```


Create a `requirements.txt` file that lists the required packages (if not already provided) for easy setup in different environments.

## Contributing

Contributions to the "Find My Plot" project are welcome! Whether it's adding new features, improving documentation, or reporting issues, we appreciate your help. Please open an issue or pull request on GitHub to contribute.

## License

Specify your licensing information here. If you have not decided on a license, [choose an open source license](https://choosealicense.com/) that best fits the project needs.

## Contact

For any questions or feedback, please open an issue on the GitHub repository, or contact the project maintainers directly via email (email@example.com).

Thank you for supporting the "Find My Plot" project!


## Mount eos
I found success running on a local desktop at CERN and needed to mount eos. 
 - [CERN EOS page](https://eos-docs.web.cern.ch/diopside/manual/hardware-installation.html#installation)
 - [This page was useful for commands](https://abpcomputing.web.cern.ch/guides/eos_on_mac/)
 - [Permissions](https://github.com/macfuse/macfuse/wiki/Getting-Started) need to be changed to mount and the getting started guide helps.
To mount the altaslocalgroupdisk
 ```
export EOS_MGM_URL=root://eosatlas/
kinit
eos fuse mount /Users/gfacini/Documents_Local/eos/
 ```
Now can do, `ls /Users/gfacini/Documents_Local/eos/atlas/atlascerngroupdisk/phys-mlf/Chatlas/`

To unmount
```
eos fuse umount /Users/gfacini/Documents_Local/eos/
```
