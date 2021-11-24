from googleapiclient.discovery import build
import json
import sys
import time
from csv import reader
from google.oauth2 import service_account
import pandas as pd
from os.path import exists



SERVICE_ACCOUNT_FILE = None
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# The ID and range of a sample spreadsheet.
OUTPUTS_MASTER_ID = None
INPUTS_EVAL_MAPPING_ID = None

sheetService = None


#########################################################


def setUpServices():
  global sheetService
  creds = service_account.Credentials.from_service_account_file( SERVICE_ACCOUNT_FILE, scopes=SCOPES )
  sheetService = build('sheets', 'v4', credentials=creds)
  #driveService = build('drive', 'v3', credentials=creds)

def stripLower(lst):
    return list(map(lambda itm: itm.strip().lower() if itm else None, lst))

def getSheetTitles(sheet, spreadsheetId):
    sheets = sheet.get(spreadsheetId=spreadsheetId, fields='sheets/properties/title').execute()
    return [sheet['properties']['title'] for sheet in sheets['sheets']]

def build_list(allCategories, INPUTS_EVAL_MAPPING_ID):
    allQuestions = []
    sheet = sheetService.spreadsheets()

    # Read the mapping of evaluator to spreadsheet ID/URL. We just use the spreadsheet ID
    total_list = []
    results = sheet.values().get(spreadsheetId=INPUTS_EVAL_MAPPING_ID,range='Sheet Mapping!A2:C').execute()
    evaluatorMap = results.get('values', [])

    # For each evaluator, iterate through each evaluation to get categories and answers
    for evaluatorEntry in evaluatorMap:
        evaluator = evaluatorEntry[0]
        print('Reading evaluator ' + evaluator)
        id = evaluatorEntry[1] # ID of this evaluator's spreadsheet
        link = evaluatorEntry[2]
        tabs = getSheetTitles(sheet, id)

        for tab in tabs[1:]:
            print(' Working on tab ' + tab)
            # ? Why R24, not E24 ?
            values = sheet.values().get(spreadsheetId=id,range=tab +'!A1:R24').execute().get('values', [])
            projectName = values[1][1].split(": ",1)[1] 
            projectNumber = projectName.split(' ')[0]
            #Generates list of categories for the specific project
            projectCategories = stripLower(values[2][1].split(": ")[1].split(', '))

            # Set up category flags for this project
            categoryFlags = ['no'] * len(allCategories)
            for category in allCategories:
                if category in projectCategories:
                    categoryFlags[allCategories.index(category)] = 'yes'
            countResponses = 0
            # Need to delay appending to allQuestions until we know # responses 
            holdQuestions = []
            # Goes through each row. For each, builds a list of the needed values
            for row in range(6,24):
                qNumber = values[row][0]
                qCategory = values[row][4]
                response = values[row][2]
                if response:
                    countResponses += 1
                short_list = [evaluator, projectNumber, projectName, link, qNumber, qCategory, response, 'no']
                short_list.extend(categoryFlags)
                holdQuestions.append(short_list)
            for row in holdQuestions:
                if (countResponses == 18):
                    row[7] = 'yes'
                allQuestions.append(row)
            time.sleep(1)


        break

    return allQuestions

# Read the list of categories, strip whitespace and lowercase them
def readCategories(OUTPUTS_MASTER_ID):
  values = sheetService.spreadsheets().values().get(spreadsheetId=OUTPUTS_MASTER_ID,range='All Data!A1:R1').execute().get('values', [])
  return stripLower(values[0][8:18])

############################ Main Program Start

#Open Json
inputs = None
if exists('./inputs.json'):
    with open('inputs.json', 'r') as file:
        inputs = json.load(file)
else:
    print('You must create an inputs.json file')
    sys.exit()

# Set global variables
OUTPUTS_MASTER_ID = inputs["OUTPUTS_MASTER_ID"]
INPUTS_EVAL_MAPPING_ID = inputs["INPUTS_EVAL_MAPPING_ID"]
SERVICE_ACCOUNT_FILE = inputs["SERVICE_ACCOUNT_FILE"]

setUpServices()

# Gets the list of categories from the master sheet
allCategories = readCategories(OUTPUTS_MASTER_ID)

# Calls list building function, creates the list to append to the spreadsheet
list_to_append = build_list(allCategories, INPUTS_EVAL_MAPPING_ID)


# Update sheet
resource = {
  "majorDimension": "ROWS",
  "values": list_to_append
}

sheetService.spreadsheets().values().update(
  spreadsheetId=OUTPUTS_MASTER_ID,
  range="All Data!A2:AA10000",
  body=resource,
  valueInputOption="USER_ENTERED").execute()



