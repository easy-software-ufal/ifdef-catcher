import json
import os
import shutil
import wget
import gdown
import zipfile
import tarfile
import glob
import re
import sys

from pathlib import Path
from xml.dom import minidom

# CONSTANTS

DOMAIN_MAP = "domain_map.json"

VERSION_0_STRING_KEY = 'previous-version'
VERSION_1_STRING_KEY = 'current-version'
VERSION_0_URL_KEY = 'previous-url'
VERSION_1_URL_KEY = 'current-url'
GOOGLE_DRIVE_FILENAME_V0 = 'google-drive-filename-v0'
GOOGLE_DRIVE_FILENAME_V1 = 'google-drive-filename-v1'
DOMAIN_KEY = 'domain'

DESTINATION_FOLDER = os.path.abspath('csv_files')
REPOS_FOLDER = os.path.abspath('repos')
CPPSTATS_INPUT_TXT = os.path.join(REPOS_FOLDER, 'cppstats_input.txt')
VERSION_0_FOLDER = os.path.join(REPOS_FOLDER, 'version_0')
VERSION_1_FOLDER = os.path.join(REPOS_FOLDER, 'version_1')
VERSION_0_SOURCE_DIR = os.path.join(VERSION_0_FOLDER, 'source')
VERSION_1_SOURCE_DIR = os.path.join(VERSION_1_FOLDER, 'source')
VERSION_0_CPPSTATS_DIR = os.path.join(VERSION_0_FOLDER, '_cppstats_discipline')
VERSION_1_CPPSTATS_DIR = os.path.join(VERSION_1_FOLDER, '_cppstats_discipline')
ANALYSIS_RESULTS_VERSION_0 = os.path.join(VERSION_0_FOLDER, 'cppstats_discipline.csv')
ANALYSIS_RESULTS_VERSION_1 = os.path.join(VERSION_1_FOLDER, 'cppstats_discipline.csv')

OUTPUT_FOLDER = "output"
TOTALS_CSV = os.path.join(OUTPUT_FOLDER, 'totals.csv')

# FUNCTIONS

def get_projects(domain_map):
    with open(domain_map, 'r') as f:
        return json.load(f)

def download(url, destiny, google_drive_filename):
    download_ok = False
    while not download_ok:
        try:
            if 'google' not in url:
                # wget
                wget.download(url, out=destiny)
            else:
                # gdown
                gdown.download(url, output = os.path.join(destiny, google_drive_filename))
            download_ok = True
        except:
            download_ok = False

def extract(files, source_dir):
    for file in files:
        if 'zip' in file:
            with zipfile.ZipFile(os.path.join(source_dir, file), 'r') as zip_ref:
                zip_ref.extractall(source_dir)
        elif 'tar.gz' in file:
            with tarfile.open(os.path.join(source_dir,file), 'r:gz') as tar_ref:
                def is_within_directory(directory, target):
                    
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)
                
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    
                    return prefix == abs_directory
                
                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")
                
                    tar.extractall(path, members, numeric_owner=numeric_owner) 
                    
                
                safe_extract(tar_ref, source_dir)
        elif 'tar.Z' in file:
            os.system('tar -zxvf ' + os.path.join(source_dir,file) + ' -C ' + source_dir)
        os.remove(os.path.join(source_dir, file))

def run_preparation():
    return 0 == os.system("cd " + REPOS_FOLDER + " && cppstats.preparation --kind discipline && cd ..")

def count_files_v1():
    total_files_v1 = 0
    for filename_1 in glob.iglob(VERSION_1_CPPSTATS_DIR + '/**/**', recursive=True):
        if not filename_1.endswith('.c') and not filename_1.endswith('.h'):
            continue
        total_files_v1 += 1
    return total_files_v1

def run_filter():
    total_files_v0 = 0
    total_deleted = 0
    total_files_v1 = count_files_v1()

    for filename_0 in glob.iglob(VERSION_0_CPPSTATS_DIR + '/**/**', recursive=True):
        if not filename_0.endswith('.c') and not filename_0.endswith('.h'):
            continue

        total_files_v0 += 1
        
        inter_0 = [f for f in os.listdir(VERSION_0_CPPSTATS_DIR)][0]
        inter_1 = [f for f in os.listdir(VERSION_1_CPPSTATS_DIR)][0]

        filename_1 = filename_0.replace(VERSION_0_FOLDER, VERSION_1_FOLDER, 1)
        filename_1 = filename_1.replace(inter_0, inter_1, 1)

        if not os.path.isfile(filename_1):
            continue
        
        with open(filename_0, 'r') as f0:
            with open(filename_1, 'r') as f1:
                print(filename_0)
                try:
                    content_0 = re.sub(r"[\n\t\s]*", "",f0.read())
                    content_1 = re.sub(r"[\n\t\s]*", "",f1.read())
                    if content_0 == content_1:
                        remove_files(filename_0)
                        remove_files(filename_1)
                    else:
                        blocks_0 = get_blocks(filename_0 + '.xml')
                        blocks_1 = get_blocks(filename_1 + '.xml')
                        if blocks_0 == blocks_1:
                            remove_files(filename_0)
                            remove_files(filename_1)
                            total_deleted += 1
                except:
                    print('error')
    
    return total_files_v0, total_files_v1, total_deleted

def get_blocks(xml_path):
    doc = minidom.parse(xml_path)
    first_node = doc.firstChild
    blocks = ""
    visitor(blocks, first_node)

    return re.sub(r"[\n\t\s]*", "", blocks)

def visitor(blocks, node):
    for child in node.childNodes:
        if child.nodeType == child.ELEMENT_NODE:
            if is_target(child):
                blocks += get_block(child)
            visitor(blocks, child)

def get_text(node):
    text = node.nodeValue if node.nodeValue != None else ''
    if not node.hasChildNodes():
        return text
    return get_text_recursive(node, text)

def get_text_recursive(node, text):
    if node == None:
        return text
    if node.nodeType == node.TEXT_NODE:
        text += node.nodeValue if node.nodeValue != None else ''
    for child in node.childNodes:
        text = get_text_recursive(child, text)
    return text

def is_target(node):
    return node.nodeName == 'cpp:if' or \
        node.nodeName == 'cpp:ifdef' or \
        node.nodeName == 'cpp:ifndef'

def get_block(node):
    block = get_text(node)
    
    endifs = 1
    sibling = node.nextSibling
    while (sibling != None):
        if sibling.nodeType == sibling.ELEMENT_NODE:
            if sibling.nodeName == 'cpp:endif':
                endifs -= 1
            elif is_target(sibling):
                endifs += 1
            
            block += get_text(sibling)
            if endifs == 0:
                break
        sibling = sibling.nextSibling

    return block

def remove_files(filepath):
    os.remove(filepath)
    os.remove(filepath + '.xml')
    n = 0
    bak_file = bak_filename(filepath, n)
    while os.path.isfile(bak_file):
        os.remove(bak_file)
        n += 1
        bak_file = bak_filename(filepath, n)

def bak_filename(filepath, n):
    return filepath + '.bak' + str(n)

def run_analysis():
    return 0 == os.system("cd " + REPOS_FOLDER + " && cppstats.analysis --kind discipline && cd ..")

def get_results(project_name, version_0, version_1):
    fix_csv_content(project_name, version_0, ANALYSIS_RESULTS_VERSION_0)
    fix_csv_content(project_name, version_1, ANALYSIS_RESULTS_VERSION_1)

    move_csv(project_name, version_0, ANALYSIS_RESULTS_VERSION_0 + '.2.csv')
    move_csv(project_name, version_1, ANALYSIS_RESULTS_VERSION_1 + '.2.csv')

def move_csv(project_name, version, csv_path):
    shutil.copyfile(csv_path, os.path.join(DESTINATION_FOLDER, project_name + '-' + version + '.csv'))

def fix_csv_content(project_name, version, csv_path):
    with open(csv_path, 'r') as f_in, open(csv_path + '.2.csv', 'w') as f_out:
        head = f_in.readline()
        f_out.write(head)

        for line in f_in:
            columns = line.split(';')
            columns[0] = project_name + '-' + version
            f_out.write(';'.join(columns))

def run(projects):
    with open(CPPSTATS_INPUT_TXT, 'w') as f:
        f.write(VERSION_0_FOLDER + '\n')
        f.write(VERSION_1_FOLDER + '\n')

    projects_stack = list(projects.keys())
    write_head_totals = True
    
    while len(projects_stack) != 0:
        project_name = projects_stack.pop()
        project = projects[project_name]

        # create version 0 and version 1 folders
        Path(VERSION_0_SOURCE_DIR).mkdir(parents=True, exist_ok=True)
        Path(VERSION_1_SOURCE_DIR).mkdir(parents=True, exist_ok=True)

        download(project[VERSION_0_URL_KEY], VERSION_0_SOURCE_DIR, project.get(GOOGLE_DRIVE_FILENAME_V0))
        download(project[VERSION_1_URL_KEY], VERSION_1_SOURCE_DIR, project.get(GOOGLE_DRIVE_FILENAME_V1))

        files_version_0 = [f for f in os.listdir(VERSION_0_SOURCE_DIR) if os.path.isfile(os.path.join(VERSION_0_SOURCE_DIR, f))]
        files_version_1 = [f for f in os.listdir(VERSION_1_SOURCE_DIR) if os.path.isfile(os.path.join(VERSION_1_SOURCE_DIR, f))]
        extract(files_version_0, VERSION_0_SOURCE_DIR)
        extract(files_version_1, VERSION_1_SOURCE_DIR)

        total_files_v0 = 0
        total_files_v1 = 0
        total_deleted = 0

        # stage 1
        if run_preparation():
            # stage 2
            total_files_v0, total_files_v1, total_deleted = run_filter()
            with open(TOTALS_CSV, 'a+') as f:
                if write_head_totals:
                    f.write("project,total files version 0,total files version 1,total removed\n")
                    write_head_totals = False
                f.write(project_name + "," + str(total_files_v0) + "," + str(total_files_v1) + "," \
                    + str(total_deleted) + "\n")

            # stage 3
            if run_analysis():
                # get results
                get_results(project_name, project[VERSION_0_STRING_KEY], project[VERSION_1_STRING_KEY])

        # delete version 0 and 1 folders
        shutil.rmtree(VERSION_0_FOLDER)
        shutil.rmtree(VERSION_1_FOLDER)

def get_total_v1_all_projects(projects):
    with open(CPPSTATS_INPUT_TXT, 'w') as f:
        f.write(VERSION_1_FOLDER + '\n')

    projects_stack = list(projects.keys())
    while len(projects_stack) != 0:
        project_name = projects_stack.pop()
        project = projects[project_name]

        Path(VERSION_1_SOURCE_DIR).mkdir(parents=True, exist_ok=True)
        download(project[VERSION_1_URL_KEY], VERSION_1_SOURCE_DIR, project.get(GOOGLE_DRIVE_FILENAME_V1))
        files_version_1 = [f for f in os.listdir(VERSION_1_SOURCE_DIR) if os.path.isfile(os.path.join(VERSION_1_SOURCE_DIR, f))]
        extract(files_version_1, VERSION_1_SOURCE_DIR)

        total_files_v1 = 0

        if run_preparation():
            total_files_v1 = count_files_v1()
            with open(os.path.join(OUTPUT_FOLDER,"totals_v1"), 'a+') as f:
                f.write(project_name + "," + str(total_files_v1) + "\n")
        shutil.rmtree(VERSION_1_FOLDER)

# MAIN

if __name__ == "__main__":
    projects = get_projects(DOMAIN_MAP)
    if len(sys.argv) > 1 and sys.argv[1] == 'count_v1':
        get_total_v1_all_projects(projects)
    else:
        run(projects)