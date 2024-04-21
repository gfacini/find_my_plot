"""
get_mentions.py

This script is designed to process a collection of experimental high-energy physics papers, extracting references to figures and tables along with their captions and mentions within the text.  It operates by searching through mmd files created by NOUGAT from PDFs compiled from LaTeX and metadata files in specified directories. It:
 - identifies patterns that denote figures and table references
 - finds urls for each figure ?

For each paper, it 
 - extracts the paper name, figures and tables mentioned,
 - constructs a structured JSON output containing these details along with URLs to the original papers (if available).

Usage:
    python get_mentions.py [dataDir] [outputDir]

Arguments:
- dataDir: Directory containing subdirectories for each paper's data, including LaTeX and metadata files.
- outputDir: Directory where the generated JSON file containing the extracted data will be saved. If do not give one, the output will go next to the input file
- outputFile: name of json file with mentions

The script also configures logging to 'log_mentions.txt', capturing important events and errors encountered during execution.

Requirements:
- Python 3.x
- Required Python packages: re, os, json, argparse, logging

This tool is part of the "Find My Plot" project aimed at enhancing accessibility to scientific figures and tables for research and review.
"""

import os
import re
import json
import logging
import argparse
import pypandoc
from datetime import datetime
from tqdm import tqdm
from collections import defaultdict

figPattern = re.compile(r"[Ff]ig. (\d+)|[Ff]igures* (\d+)")
# don't take lines that end in hline to avoid tables listing tables
tablePattern = re.compile(r"[Tt]able (\d+)(?!.*\\hline$)")
figIdentifier = "Figure "
tableIdentifier = "Table "
LATEX_FILE = "latex.txt"
META_FILE = "meta_info.txt"

def snipSentence(line, m):
    sentenceBefore = line[:m.start()].split(". ")[-1]
    sentenceAfter = line[m.end():].split(". ")[0]
    return sentenceBefore + m.group(0) + sentenceAfter 

def getLinesFromFile(folderLoc, file):
    fileLoc = os.path.join(folderLoc, file)
    with open(fileLoc, encoding="utf8") as f:
        return f.readlines()

def extractImageNamesAndMentions(allLines, pattern, identifier):
    mentions = defaultdict(list)
    for line in allLines:
        for m in re.finditer(pattern, line):
            index = next(g for g in m.groups() if g is not None)
            mentions[identifier + index].append(snipSentence(line, m))
    return dict(mentions)

def extractPaperName(metaLinesList):
    paperNameLines = []
    capture = False
    for line in metaLinesList:
        if 'PAPER NAME :' in line:
            capture = True
            paperName = line.split('PAPER NAME :', 1)[1].strip()
            paperNameLines.append(paperName)
        elif 'LAST MODIFICATION DATE :' in line and capture:
            capture = False
            break
        elif capture:
            paperNameLines.append(line.strip())
    return ' '.join(paperNameLines) if paperNameLines else None

def convert_latex_to_text(latex_content):
    # Convert LaTeX to plain text
    try:
        text_output = pypandoc.convert_text(latex_content, 'plain', format='latex')
        return text_output 
    except RuntimeError as e:
        print(f"An error occurred during conversion: {e}") 
        logging.error(f"An error occurred during conversion: {e}") 
        logging.error(f"\t{latex_content}")
        return latex_content

def preprocess_text(text):
    '''
    Remove basic latex things we don't need pandoc for. If anything left, call pandoc
    '''
    # Replace or remove LaTeX-specific sequences
    replacements = {
            "\\)": ")",
            "\\(": "(",
            "\\rm ": "",        # Remove \rm which is often used for font style in math mode
            "\\cal ": "",       # Remove \cal which is used for calligraphic style
            "\\pm": "±",       # Replace \pm with the actual plus-minus symbol
            #"\\\\": "",         # Remove double backslashes
            "\\,": "",          # Remove small space often used in LaTeX
            "\\;": "",          # Remove thicker space often used in LaTeX
            "\\quad": "  ",     # Replace quad space with two spaces
            "\\qquad": "    ",  # Replace double quad space with four spaces
            "\n": " ",          # newline
            "\r\n": " ",        # other style newline (Windows?)
            # add more replacements as needed
            }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # whole sale delete 
    # Figures referenced in Tables will cause the table data to be passed through pandoc which chokes on \begin??
    if "\\begin" in text: text = ""

    # Check for double backslashes as a sign of LaTeX
    if "\\" in text: 
        # Call pandoc or handle LaTeX here
        text = convert_latex_to_text(text)

        # Remove new lines
        if text is not None:
            text = text.replace("\n", " ")

    return text
                

def process_directories(dataDir, outputDir, outputFile):

    # Process each subdirectory in the input directory
    for f in tqdm(os.listdir(dataDir),desc="Documets: "):
        folderDir = os.path.join(dataDir, f)
        if outputDir is None:
            outputDir = folderDir
        else:
            # maintain folder structure but lose collection information
            outputDir = outputDir + f

        process_directory(folderDir, outputDir, outputFile)


def process_directory(folderDir, outputDir, outputFile):
    logging.info(f"\nProcessing {folderDir}")
    # Skip if is not a directory
    if not os.path.isdir(folderDir):
        return
    
    # Attempt to read the latex and metadata files, skip the folder if either file is missing
    try:
        latexLinesList = getLinesFromFile(folderDir, LATEX_FILE)
    except FileNotFoundError:
        logging.error(f"{LATEX_FILE} not found in: {folderDir}")
        return

    try:
        metaLinesList = getLinesFromFile(folderDir, META_FILE)
    except FileNotFoundError:
        logging.error(f"{META_FILE} not found in: {folderDir}")
        return

    # Extract the paper name from the metadata file
    paperName = extractPaperName(metaLinesList)

    # Extract the URL from the last line of the metadata file
    atlusUrl = max(metaLinesList[-1].split(), key=len)

    # Extract mentions of figures and tables from the latex file
    figMentionDic   = extractImageNamesAndMentions(latexLinesList, figPattern, figIdentifier)
    tableMentionDic = extractImageNamesAndMentions(latexLinesList, tablePattern, tableIdentifier)

    # Combine figure and table mentions into a single dictionary
    combinedMentionDic = {**figMentionDic, **tableMentionDic}

    # Compile the data for each figure/table into a list of dictionaries
    figures = []
    mentions_text = defaultdict(list)

    for key, texts in combinedMentionDic.items():
        # process texts and fill new dictionary
        texts_preprocessed = [preprocess_text(text) for text in texts]
        mentions_text[key] = texts_preprocessed
        #print(f"Key: {key}, Processed Texts: {texts_preprocessed}")
        
        figures.append({
            "name": key, 
            "mentions": mentions_text, 
            "atlusUrl": atlusUrl, 
            "paper": os.path.basename(folderDir), 
            "paperName": paperName
        })

    # Define the path and name for the output JSON file
    outputFilePath = os.path.join(folderDir, outputFile)

    # delete if exists - "w" not working below?
    if os.path.exists(outputFilePath):
        os.remove(outputFilePath)
    
    # Write the compiled data to the output JSON file
    with open(outputFilePath, "w", encoding="utf-8") as outfile:
        json.dump(figures, outfile, indent=4, ensure_ascii=False)
    

def ensure_trailing_slash(path):
    return path if path.endswith("/") else path + "/"

def main():
    parser = argparse.ArgumentParser(description='Process paper directories.')

    # default values assume running from base directory of repo
    parser.add_argument('dataDir', type=str, help='Input directory containing paper data',
                        default='paper data\CMS-papers\CDS_doc', nargs='?')
    parser.add_argument('outputDir', type=str, help='Output directory for the generated data',
                        default=None, nargs='?')
    parser.add_argument('outputFile', type=str, help='Output file for the generated data',
                        default='figures_and_tables_text.json', nargs='?')

    args = parser.parse_args()

    print("Running get-metions.py with args:")
    print(f"\t--dataDir:    {args.dataDir}")
    print(f"\t--outputDir:  {args.outputDir}")
    print(f"\t--outputFile: {args.outputFile}")

    # Setup logging to file
    logfile_name = "log_mentions_" + (datetime.now()).strftime("%Y%m%d_%H%M%S") + ".txt"
    logfile_dir = ensure_trailing_slash(args.dataDir) 
    if args.outputDir is not None:
    logging.basicConfig(filename=logfile, level=logging.INFO, 
            format='%(asctime)s:%(levelname)s:%(message)s')

    logging.info("Running get-metions.py with args:")
    logging.info(f"\t--dataDir:    {args.dataDir}")
    logging.info(f"\t--outputDir:  {args.outputDir}")
    logging.info(f"\t--outputFile: {args.outputFile}")

    # Rest of the main function remains the same
    if not os.path.isdir(args.dataDir):
        logging.error(f"Input directory not found: {args.dataDir}")
        exit(1)

    outputDir = args.outputDir
    if args.outputDir is not None:
        if not os.path.isdir(args.outputDir):
            logging.info(f"Output directory not found, trying to create: {args.outputDir}")
            try:
                os.makedirs(args.outputDir)
            except OSError as error:
                logging.error(f"Failed to create output directory: {error}")
                exit(1)
        outputDir = ensure_trailing_slash(outputDir)

    # easiest way to get the acutal pandoc package when cannot do sudo apt-get install pandoc
    pypandoc.download_pandoc()

    process_directories(ensure_trailing_slash(args.dataDir), 
                        outputDir,
                        args.outputFile)

if __name__ == "__main__":
    main()

