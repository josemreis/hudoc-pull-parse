#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul 14 14:12:42 2020

@author: jmr
"""
import requests
import pandas as pd
from pandas.io.json import json_normalize
from random import randint
from time import sleep
from glob import glob
import re
import os
from expressvpn import wrapper

## vpn funs
# status of vpn
def vpn_status():
    p = subprocess.Popen("expressvpn status", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    return list([str(v).replace('\\t', ' ').replace('\\n', ' ').replace('b\'', '').replace('\'', '')
                .replace('b"', '')
                 for v in iter(p.stdout.readline, b'')])

# random vpn
def random_vpn():
    wrapper.random_connect()
    return

## load case ids
def load_caseids(case_data_dir = '/home/jmr/Dropbox/Current projects/thesis_papers/transparency, media, and compliance with HR Rulings/ecthr_media&compliance/data/pluriCourtsGeorgeTown_data/DirectingComplianceReplication_data/DirectingComplianceReplicationDataApril2019.csv',
               case_id_var = 'application.number'):
    ## load
    comp = pd.read_csv(case_data_dir)
    ## Extract the relevant app_numbers - the ones for which we have compliance data
    app_numbers = list(set(comp[case_id_var]))
    return app_numbers

## hudoc query
def make_hudoc_query(case_id, max_retries = 5, max_sleep = 5, doctype_regex = 'JUD|CLI|COM|PR', debug = True):
    """
    Make a doc query in hudoc using case_id. Covers all types of jdugment related docs.
    * case_id: case id (str)
    * max_retries: if failing, how many times to repeat the HTTP GET request (int)
    * doctype_regex: regex expression for type of docs to retrieve (str). Default filter judgments, information notes, press-releases, and communications.
    RETURNS -> pandas dataframe
    """
    ## prep the url
    query_url = """https://hudoc.echr.coe.int/app/query/results?query=contentsitename:ECHR AND (NOT (doctype=PR OR doctype=HFCOMOLD OR doctype=HECOMOLD)) AND ((appno:"{case_id}")) AND ((documentcollectionid="JUDGMENTS") OR (documentcollectionid="COMMUNICATEDCASES") OR (documentcollectionid="CLIN") OR (documentcollectionid="ADVISORYOPINIONS") OR (documentcollectionid="REPORTS") OR (documentcollectionid="RESOLUTIONS"))&select=sharepointid,Rank,ECHRRanking,languagenumber,itemid,docname,doctype,application,appno,conclusion,importance,originatingbody,typedescription,kpdate,kpdateAsText,documentcollectionid,documentcollectionid2,languageisocode,extractedappno,isplaceholder,doctypebranch,respondent,advopidentifier,advopstatus,ecli,appnoparts,sclappnos&sort=&start=0&length=20&rankingModelId=22222222-eeee-0000-0000-000000000000""".format(case_id = case_id)
    ## make a GET request
    attempt = 0
    while True:
        attempt += 1
        try:
            response = requests.get(query_url)
            if not response.ok:
                print("\tFailed to query %s"%(case_id))
                print("\tURL: %s"%(query_url))
                continue
            else:
                # pull the json response
                resp_json = response.json()
                # turn to pandas
                out = json_normalize(resp_json['results'])
                # clean up column names
                out.columns = out.columns.str.replace("columns.", "")
                # break the while loop
                sleep(randint(0, max_sleep))
                break
        except:
            if attempt > max_retries:
                print("\tFailed to query %s"%(case_id))
                print("\tURL: %s"%(query_url))
                raise TypeError('no docs were retrieved for case: ' + case_id)
            else:
                print("\tFailed to query %s"%(case_id) + " retrying in few seconds")
                sleep(randint(10, 30))
                continue
    ## filter out empty docs and return
    if isinstance(out, pd.core.frame.DataFrame):
        ret = out[( out['application'].str.contains("WORD") ) & ( out['appno'].str.contains(case_id) ) & (out['doctype'].str.contains(doctype_regex))]
    else:
        print("no documents retrieved for %s"%(case_id))
        ret = None
    if debug:
        print(ret)
    return ret

## make filename
def make_filename(base_dir, case_id, doctype, languageisocode, application):
    if "WORD" in application:
        ## as docx
        file_type = ".docx"
    elif application in ['PDF', 'ACROBAT']:
        ## as pdf
        file_type = ".pdf"
    else:
        file_type = None
    if file_type != None:
        ret = base_dir + "_".join([languageisocode, doctype, case_id.replace("/", "_")]) + file_type
    return ret
    
## Saving the word document
def get_doc(item_id, filename, max_retries = 5):
    """
    Takes a link for a document and saves it in a given filename
    * doc_url: url for downloading the document (str)
    * filename: filename (str)
    see: https://stackoverflow.com/questions/48800385/how-to-download-ms-word-docx-file-in-python-with-raw-data-from-http-url
    """
    ## make doc url
    doc_url = "https://hudoc.echr.coe.int/app/conversion/docx/?library=ECHR&id={item_id}&filename={filename}".format(item_id = item_id, filename = filename)
    attempt = 0
    while True:
        attempt += 1
        try:
            the_file = requests.get(doc_url, stream=True)  
            download_it = True
            if not the_file.ok:
                print("\tFailed to download %s"%(filename))
                print("\tURL: %s"%(doc_url))
                continue
            else:
                break
        except:
            download_it = False
            if attempt > max_retries:
                print("\tFailed to download %s"%(filename))
                break
            else:
                print("\tretry number %s"%(attempt))
                sleep(randint(8, 15))
    if download_it:
        with open(filename, 'wb') as f:
          for chunk in the_file.iter_content(1024^2):  # 2 MB chunks
            f.write(chunk)

## main function for pulling or rulings and other docs in all available languages
def main():
    ## load case ids
    case_ids = load_caseids()
    ## filter out the collected ones
    # output directory
    base_dir = '/home/jmr/Dropbox/Current projects/thesis_papers/transparency, media, and compliance with HR Rulings/ecthr_media&compliance/data/case_docs_data/rulings_dir/'
    # existing files
    cur_files = glob(base_dir + "*")
    # extract the ids
    pattern = re.compile('[0-9]+\_[0-9]+')
    done = []
    for file in cur_files:
        file_match = pattern.findall(file)
        if len(file_match) > 0:
            done.append(file_match[0].replace("_", "/"))
    ## unique ids
    done = list(set(done))
    ## start the loop
    print(str(len(case_ids) - len(done)) + " to go...")
    for cur_id in case_ids:
        if cur_id not in done:
            print("\npulling docs for case " + cur_id + "\n")
            ## make query for available docs related with case
            doc_data = make_hudoc_query(case_id = cur_id, max_retries = 10, max_sleep = 2, debug = True) 
            ## For each document, make file name and download
            if isinstance(doc_data, pd.core.frame.DataFrame):
                for index, row in doc_data.iterrows(): 
                    ## get the relevant vars
                    app_no = row['appno']
                    doc_type = row['doctype']
                    lang = row['languageisocode']
                    app = row['application']
                    item_id = row['itemid']
                    ## make the filename
                    filename = make_filename(base_dir, cur_id, doc_type, lang, app)
                    if os.path.isfile(filename) == False:
                        ## download it
                        print("Downloading\n" + filename)
                        get_doc(item_id, filename)
                        sleep(randint(0, 2))
            else:
                raise TypeError('no docs were retrieved for case: ' + case_id)

## run
if __name__ == "__main__":
    for run in range(1, 20):
        print("\n run: " + str(run) + "\n")
        try:
            main()
        except Exception as e:
            print(e)
            # switch vpn
            random_vpn()
            sleep(randint(10, 20))
    