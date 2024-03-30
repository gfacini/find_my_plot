"""
Scrapes CDS documents from specified URLs and processes the documents to extract metadata, download PDFs, and convert content to markdown.
This script is designed for batch processing of documents from the CERN Document Server (CDS).

Requirements: nougat package from META, PyPDF2 and BeautifulSoup. See README in base directory for venv setup.

Original Author: Runze Li
Email: runze.li@yale.edu

Mar 2023 G.Facini (UCL)
 - Modified to take args, main
 - Flags for overwriting
 - Allow for pdf downloads and nougat running sepately
 - Write plot URLS to meta_info

Usage:
    python cds_scrape.py --base_url <CDS Base URL> --depth <Depth> --output_dir <Output Directory>
"""

import os, glob, re, subprocess, shutil
from bs4 import BeautifulSoup
import PyPDF2
import requests
import argparse
from datetime import datetime

def url_to_folder_name(url):
    """
    Converts a CDS document URL to a standardized folder name based on the record number.

    Args:
        url (str): The URL of the CDS document.

    Returns:
        str: A folder name in the format "CDS_Record_<record_number>" or "Invalid_URL" if the URL pattern doesn't match.
    """
    match = re.search(r'record/(\d+)', url)
    if match:
        return f"CDS_Record_{match.group(1)}"
    else:
        return "Invalid_URL"

def min_of_list(values):
    """
    Finds the minimum value in a list, ignoring None values.

    Args:
        values (list): A list of values which can include None.

    Returns:
        int: The minimum value in the list, or -1 if the list is empty or contains only None values.
    """
    filtered_values = [v for v in values if v is not None]
    return min(filtered_values) if filtered_values else -1

def is_atlas_link(link):
    """Check if the link is a ATLAS link."""
    return 'atlas.web.cern.ch/Atlas' in link

def is_cms_link(link):
    """Check if the link is a CMS link."""
    return 'cms-results.web.cern.ch/cms-results' in link

def is_cds_Figure_link(link):
    return 'cds.cern.ch/record' in link and "Figure" in link

def get_plot_location(soup, url):
    """
    Look for location of plots webpage. 
     - For recent papers it is in the CDS notes field
     - For recent ATLAS PUB and CONF it is also in the notes field
     - For CMS PAS, they are linked to CDS directly - looking for a "cds link"
     - For older things, return None

     Input:
      soup from BeautifulSoup of CDS Record
      url in case the answer is CDS
     """

    # first look for a url in the Note of the cds record
    note_item = soup.find('td', class_='formatRecordLabel', string='Note')
    if note_item:
        note_row = note_item.find_parent('tr')
        if note_row:
            link_tag = note_row.find('a')
            if link_tag:
                url = link_tag.get('href')
                return url

    # if not, do a generic look for atlas links
    atlas_link = soup.find('a', href=lambda href: href and is_atlas_link(href))
    if atlas_link:
        return atlas_link['href']

    # if not, do a generic look for cms links
    cms_link = soup.find('a', href=lambda href: href and is_cms_link(href))
    if cms_link:
        return cms_link['href']

    # Look for CDS links
    # Find all <meta> tags with property="og:image" or property="og:image:secure_url" that contain the desired links
    figure_links = [meta['content'] for meta in soup.find_all('meta', attrs={'property': lambda x: x in ['og:image', 'og:image:secure_url']}) if is_cds_Figure_link(meta.get('content', ''))]
    if len(figure_links) > 0:
        return url

    # check if ATLAS paper without link in notes but name of PDF tells us it is a paper
    meta_tag = soup.find('meta', attrs={'name': 'citation_pdf_url'})
    if meta_tag:
        pdf_url = meta_tag['content']
        pdf_name = pdf_url.split("/")[-1][:-4] # cut off .pdf
        if "PAPER" in pdf_name: # then has form with something like: ANA-EXOT-2019-01-PAPER.pdf
            pdf_name = pdf_name.replace("ANA-","")
            pdf_name = pdf_name.replace("-PAPER.pdf","")
            maybe_url = f"https://atlas.web.cern.ch/Atlas/GROUPS/PHYSICS/PAPERS/{pdf_name}"
            response = requests.get(maybe_url)
            if response.status_code == 200: return maybe_url

    return "None"


def download_pdf(url, paper_folder, overwrite=False):
    """
    Downloads the PDF from a given paper's CDS record URL
    It also parses the meta data in the url for the technical report number(s) and plot location
    If the file exists and overwrite is False, the pdf is not downloaded

    Args:
        url (str)   : The URL of the paper on CDS.
        paper_folder: Path to directory where paper is downloaded (assumed to exist) 
        overwrite   : T/F. If false and pdf exists locally, return the name like it was downloaded

    Returns: 
        str : The full path of the (downloaded) PDF file, or None if download fails or the meta tag is not found.
        list: technical report number
        str : plot location will be URL for experiment page that holds all PDFs, URL to CDS if all listed there, or None if noe of those are satisfied
        
    """
    print("Downloading document")
    print(f"\t url: {url}")
    #print(f"\t out: {paper_folder}")
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    meta_tag = soup.find('meta', attrs={'name': 'citation_pdf_url'})

    tech_report_num = []
    plot_loc = "None"

    if not meta_tag:
        print('No citation_pdf_url meta tag found.')
        return None, tech_report_num, plot_loc 

    pdf_url = meta_tag['content']
    pdf_name = pdf_url.split("/")[-1][:-4] # cut off .pdf
    full_path = f"{paper_folder}/{pdf_name}.pdf"
    print(f"\t out: {full_path}")
   
    # get technical report
    # sometimes there are multiple
    meta_numbers = soup.find_all('meta', attrs={'name': 'citation_technical_report_number'})
    tech_report_num = [meta['content'] for meta in meta_numbers if meta and meta.get('content')]

    # get plot location
    plot_loc = get_plot_location(soup, url)

    # check if pdf exists
    if os.path.exists(full_path):
        if overwrite: # clean the existing pdf
            os.remove(full_path)
        else: # don't overwrite so return name and proceed
            print("PDF exists, and not overwriting")
            return full_path, tech_report_num, plot_loc

    response_pdf = requests.get(pdf_url) # get the pdf
    if response_pdf.status_code == 200:
        with open(full_path, 'wb') as f:
            f.write(response_pdf.content)
            f.close()
            print("Wrote file")
    else:
        print(f'Failed to download PDF from {pdf_url}')
        return None, tech_report_num, plot_loc

    return full_path, tech_report_num, plot_loc

def get_modification_date(url):
    """
    Extracts the last modification date from a paper's CDS page.

    Args:
        url (str): The URL of the paper on CDS.

    Returns:
        str: The last modification date as a string, or None if not found.
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    modification_div = soup.find("div", class_="recordlastmodifiedbox")

    if modification_div:
        return modification_div.get_text(strip=True).split("last modified")[-1].strip()
    else:
        return "2001-01-01" # dummy date

def extract_text(file, output_directory, page_to_stop):
    """
    Uses the nougat tool to extract text from a PDF file.

    Args:
        file (str): The full path of the PDF file.
        output_directory (str): The directory where the extracted text should be saved.
        page_to_stop (int): The last page number to include in the extraction.
    """
    cmd = ["nougat", file, "-o", output_directory]
    if page_to_stop != -1:
        cmd += ["-p", f"1-{page_to_stop}"]

    try:
        process = subprocess.Popen(cmd)
        process.wait()
        # rename? no - pdf name corresponds to the arXiv
        if process.returncode == 0:
            #os.rename(output_directory + file_dir + ".mmd", output_directory + "document.mmd")
            print("NOUGAT ended successfully")
        else:
            print(f"Process ended with an error code: {process.returncode}")
    except Exception as e:
        print("An error occurred during text extraction:", e)

def find_key_in_pdf(file, keyword):
    """
    Searches for a keyword in a PDF file and returns the page number where it's found.

    Args:
        file_path (str): The path to the PDF file.
        keyword (str): The keyword to search for.

    Returns:
        int: The 1-indexed page number where the keyword is found, or None if not found.
    """
    try:
        with open(file, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages) - 1, -1, -1):
                text = reader.pages[page_num].extract_text()
                if text and keyword in text:
                    return page_num + 1
    except Exception as e:
        print("Error searching PDF:", e)
    return None

def get_paper_links(url):
    """
    Retrieves all paper links and their titles from a CDS search page.

    Args:
        url (str): The URL of the CDS search page.

    Returns:
        tuple: Two lists, one with paper links and one with their corresponding titles.
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    paper_links, paper_titles = [], []

    for titlelink in soup.find_all('a', class_='titlelink'):
        title = titlelink.text
        link = titlelink['href']
        if "[...]" not in title:
            paper_links.append(link[:-6] if link.endswith("?ln=en") else link)
            paper_titles.append(title)
    
    return paper_links, paper_titles


def write_to_db(args, overwrite=False):
    """
    Scrapes CDS documents based on a base URL and depth, downloads PDFs, extracts metadata, and saves data to a database.

    Args:
        collection (str): The CDS search collection. Use spaces
        depth (int): How many pages deep to scrape.
        db_dir (str): The directory where the scraped data should be stored.
        run_nougat (T/F): run nougat or not
        overwrite (T/F): overwrite existing files, but only if the pdf has been updated
    """

    # input args
    collection  =  args.collection
    start       =  args.start
    depth       =  args.depth
    count       =  args.count
    db_dir      =  args.output_dir
    run_nougat  =  args.run_nougat

    # build url to get 10 results per results page
    base_url = "https://cds.cern.ch/search?cc=" + collection.replace(" ","+") + "&rg=10" + "m1=a&jrec={page_index}"
    print(base_url)

    if count:
        #base_url = base_url + "&of=id"
        url = base_url.format(page_index="1")
        response = requests.get(url)
        number_of_records = -1
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
# Find the specific <td> element that contains the number
            td_with_number = soup.find('td', class_='searchresultsboxheader', align='center')
            if td_with_number:
                # Within this <td>, find the <strong> tag that contains the number
                strong_tag = td_with_number.find('strong')
                if strong_tag:
                    number_of_records = strong_tag.text.strip().replace(',', '')  # Remove commas for clean number extraction

            print(f"Records: {number_of_records}")

        return 

    # output directory
    base_dir = db_dir + "/" + collection.replace(" ","_")
    if not os.path.exists(base_dir):
        os.mkdir(base_dir)

    fail_file = open(base_dir+"/failed_list.txt", 'a')
    total = 0

    get_more = True # flag to control if go to next results page or not
    result_page = start
    while get_more:

        if depth >= 0 and result_page > depth:
            print("Reached depth. Ending the scraping process.")
            break

        print("Results page "  + str(result_page) + " (depth= " + str(depth) + ")")

        # so depth is n, then i is 1, 11, ..., 10*(n-1) + 1
        page_index = result_page * 10 + 1

        # get the url of this page
        url = base_url.format(page_index=page_index)

        # loop through all links on this results page, 
        # should find 10 paper links
        links, titles = get_paper_links(url)

        # Check if no links were found, indicating we might have reached the end
        if not links:
            print("No more papers found. Ending the scraping process.")
            break

        for link, title in zip(links, titles):

            print("\nwork on link " + link)
            folder_name = url_to_folder_name(link)
            last_modification_date = get_modification_date(link)

            paper_folder = base_dir + "/" + folder_name
            if not os.path.exists(paper_folder): os.mkdir(paper_folder)

            # check if updated since late write
            updated = True # default to true in case first time looking at entry
            if os.path.exists(paper_folder + "/meta_info.txt"):
                saved_date = None
                with open(paper_folder + "/meta_info.txt", "r") as meta_info:
                    for line in meta_info:
                        if line.startswith("LAST MODIFICATION DATE :"):
                            saved_date = line.split(":")[1].strip()  # Extract the date part and strip whitespace
                            break  # Exit the loop once the date is found
                if saved_date is not None:
                    print("Saved date:", saved_date)

                    # Convert both date strings to datetime objects
                    saved_date_dt = datetime.strptime(saved_date, "%Y-%m-%d")
                    new_date_dt = datetime.strptime(last_modification_date, "%Y-%m-%d")

                    # Now can compare, if new date later, need to updated
                    if saved_date_dt < new_date_dt:
                        print(f"PDF has been updated! Overwrite set to {overwrite}")
                    else:
                        updated = False

            # Get the PDF
            pdf_overwrite = overwrite 
            if overwrite and not updated: pdf_overwrite = False # don't download if wasn't changed
            pdf_name, tech_rep_num, plot_loc = download_pdf(link,paper_folder,pdf_overwrite)

            if pdf_name == None:
                fail_file.write(link + "\n")
                print("\n fail to read " + link + "\n")
                continue

            if updated or overwrite:
                print("\tWriting metadata")
                meta_info = open(paper_folder + "/meta_info.txt", 'w')
                meta_info.write("PAPER NAME : ")
                meta_info.write(title.replace("\n", "")+"\n")
                meta_info.write("LAST MODIFICATION DATE : ")
                meta_info.write(last_modification_date + "\n")
                meta_info.write("URL : ")
                meta_info.write(link.replace("\n", "") + "\n")
                meta_info.write("COLLECTION : ")
                meta_info.write(collection.replace(" ", "_") + "\n")
                meta_info.write("TECH REP NUM: ")
                meta_info.write(', '.join(tech_rep_num))
                meta_info.write("\n")
                meta_info.write(f"PLOT LOC: {plot_loc}\n")
                meta_info.close()

            mmd_update = run_nougat # start with if user asked to run_nougat
            # if it exits, check overwrite and updated
            if os.path.exists(paper_folder + "/document.mmd"):
                mmd_update = run_nougat and overwrite
                if mmd_update:
                    os.remove(paper_folder + "/document.mmd")
            if mmd_update: 
                try:
                    last_page_num_References = find_key_in_pdf(pdf_name, "References")
                    #last_page_num_The_ATLAS_Collaboration = find_key_in_pdf(pdf_name, "The ATLAS Collaboration")  
                    #remove this because sometimes it shows up in the very beginning :(
                    last_page_num_acknowledgement = find_key_in_pdf(pdf_name, "ACKNOWLEDGMENT")
                    page_to_stop = min_of_list([last_page_num_References, last_page_num_acknowledgement])
                    # control with flag TODO
                    #print("last reference at " + str(last_page_num_References) + " last acknowledge at " + str(last_page_num_acknowledgement))
                    #print("end at " + str(page_to_stop))
                    extract_text(pdf_name, paper_folder + "/", page_to_stop)
                except:
                    fail_file.write(link + "\n")
                    print("\n fail to read " + link + "\n")
    
            # add flag to remove pdf
            #if os.path.exists(pdf_name):
            #    os.remove(pdf_name)
    
        result_page = result_page + 1
        # end while

    print(f"Total entries: {total}")

    fail_file.close()

def main():
    parser = argparse.ArgumentParser(description="Scrapes CDS documents and processes them.")
    parser.add_argument("--collection", type=str, help="CDS Collection i.e. 'ATLAS Papers'", required=True)
    parser.add_argument("--start", type=int, default=0, help="Start to scrape.", required=False)
    parser.add_argument("--depth", type=int, help="Depth to scrape.", required=True)
    parser.add_argument("--count", action='store_true', help="Count titles", required=False)
    parser.add_argument("--output_dir", type=str, help="Directory to store output.", required=True)
    parser.add_argument("--run_nougat", action='store_true', help="Flag to control execution of nougat on the PDFs from search results.")
    parser.add_argument("--pdf_nougat", action='store_true', help="Flag to control execution of nougat on a set of PDFs.")

    args = parser.parse_args()
    print("Running scrapeCDS.py with args:")
    print(args)

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    if args.pdf_nougat:
        # Pattern to match PDF files within cds_data/*/*/*.pdf
        pattern = f"{args.output_dir}/{args.collection}/CDS_*/*.pdf"

        # Use glob.glob to find all files matching the pattern
        pdf_files = glob.glob(pattern)
        
        # Loop through the found PDF files
        for pdf_file in pdf_files:
            output_dir = os.path.dirname(pdf_file)
            last_page_num_References = find_key_in_pdf(pdf_name, "References")
            last_page_num_acknowledgement = find_key_in_pdf(pdf_name, "ACKNOWLEDGMENT")
            page_to_stop = min_of_list([last_page_num_References, last_page_num_acknowledgement])
            extract_text(file, output_dir, page_to_stop)

    else:
        # Call the write_to_db function with the additional flags
        write_to_db(args, True)



if __name__ == "__main__":
    main()

