#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
COMP9321 24T1 Assignment 2
Data publication as a RESTful service API

Getting Started
---------------

1. You MUST rename this file according to your zID, e.g., z1234567.py.

2. To ensure your submission can be marked correctly, you're strongly encouraged
   to create a new virtual environment for this assignment.  Please see the
   instructions in the assignment 1 specification to create and activate a
   virtual environment.

3. Once you have activated your virtual environment, you need to install the
   following, required packages:

   pip install python-dotenv==1.0.1
   pip install google-generativeai==0.4.1

   You may also use any of the packages we've used in the weekly labs.
   The most likely ones you'll want to install are:

   pip install flask==3.0.2
   pip install flask_restx==1.3.0
   pip install requests==2.31.0

4. Create a file called `.env` in the same directory as this file.  This file
   will contain the Google API key you generatea in the next step.

5. Go to the following page, click on the link to "Get an API key", and follow
   the instructions to generate an API key:

   https://ai.google.dev/tutorials/python_quickstart

6. Add the following line to your `.env` file, replacing `your-api-key` with
   the API key you generated, and save the file:

   GOOGLE_API_KEY=your-api-key

7. You can now start implementing your solution. You are free to edit this file how you like, but keep it readable
   such that a marker can read and understand your code if necessary for partial marks.

Submission
----------

You need to submit this Python file and a `requirements.txt` file.

The `requirements.txt` file should list all the Python packages your code relies
on, and their versions.  You can generate this file by running the following
command while your virtual environment is active:

pip freeze > requirements.txt

You can submit the two files using the following command when connected to CSE,
and assuming the files are in the current directory (remember to replace `zid`
with your actual zID, i.e. the name of this file after renaming it):

give cs9321 assign2 zid.py requirements.txt

You can also submit through WebCMS3, using the tab at the top of the assignment
page.

"""

# You can import more modules from the standard library here if you need them
# (which you will, e.g. sqlite3).
import os
from pathlib import Path

# You can import more third-party packages here if you need them, provided
# that they've been used in the weekly labs, or specified in this assignment,
# and their versions match.
from dotenv import load_dotenv          # Needed to load the environment variables from the .env file
import google.generativeai as genai     # Needed to access the Generative AI API
from flask import Flask, request,send_file
from flask_restx import Resource, Api,reqparse, fields
import requests
from datetime import datetime
import sqlite3
from pandas.io import sql
import pandas as pd
from datetime import datetime, timedelta, timezone

app = Flask(__name__)
api = Api(app, title = 'A smart API for the Deutsche Bahn')
indicator_model = api.model('Q5payload',{
        'name': fields.String(description='The name of the stop'),
        'latitude': fields.Float(description='Latitude of the stop'),
        'longitude': fields.Float(description='Longitude of the stop'),
        'last_updated': fields.String(description='The last update time in yyyy-mm-dd-hh:mm:ss format', required=False),
        'next_departure': fields.String(description='Next departure details')
    })
studentid = Path(__file__).stem         # Will capture your zID from the filename.
db_file   = f"{studentid}.db"           # Use this variable when referencing the SQLite database file.
txt_file  = f"{studentid}.txt"          # Use this variable when referencing the txt file for Q7.


# Load the environment variables from the .env file
load_dotenv('.env')

# Configure the API key
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# Create a Gemini Pro model
gemini = genai.GenerativeModel('gemini-pro')

parser_query = reqparse.RequestParser()
parser_query.add_argument("query")
parser_query2 = reqparse.RequestParser()
parser_query2.add_argument("include")

def db_connection():
   cnx = sqlite3.connect(db_file)
   return cnx

def init():
   cnx = db_connection()
   # create db_file in current dir
   cursor = cnx.cursor()
   
   create_table_query = '''
      CREATE TABLE IF NOT EXISTS stops (
         stop_id INTEGER PRIMARY KEY,
         last_updated TEXT NOT NULL,
         name TEXT NOT NULL,
         latitude REAL NOT NULL,
         longitude REAL NOT NULL
      );
      '''
   # Use the cursor to execute the SQL statement.
   cursor.execute(create_table_query)
   # Commit changes
   cnx.commit()
   cnx.close()
  

init()




def db_read(stop_id):
   cnx = db_connection()
   cursor = cnx.cursor()
   cursor.execute('SELECT * FROM stops WHERE stop_id = ?', (stop_id,))
   result = cursor.fetchall()
   cnx.close()
   return result

def db_insert(stop_id, last_updated, name, latitude, longitude): # insert data
   cnx = db_connection()
   cursor = cnx.cursor()
   query = 'INSERT INTO stops (stop_id, last_updated, name, latitude, longitude) VALUES (?, ?, ?, ?, ?)'
   cursor.execute(query, (stop_id, last_updated, name, latitude, longitude))
   cnx.commit()
   cnx.close()

def db_update(stop_id, last_updated, name, latitude, longitude): 
   cnx = db_connection()
   cursor = cnx.cursor()
   query = 'UPDATE stops SET last_updated = ?, name = ?, latitude = ?, longitude = ? WHERE stop_id = ?'
   cursor.execute(query, (last_updated, name, latitude, longitude, stop_id))
   # 提交事务
   cnx.commit()
   cnx.close()


def db_delete(stop_id):
   cnx = db_connection()
   cursor = cnx.cursor()
   delete_query = "DELETE FROM stops WHERE stop_id = ?"
   cursor.execute(delete_query, (stop_id,))
   # 提交事务
   cnx.commit()
   cnx.close()

def get_next_departure(stop_id):
    url = f'https://v6.db.transport.rest/stops/{stop_id}/departures'
    response = requests.get(url)
    if response.status_code == 200:
        departures = response.json()
        for departure in departures['departures']:
            if departure['platform'] and departure['direction']:
               
               current_time = datetime.now(timezone.utc)
               maximum_from_now = current_time + timedelta(minutes=120)
               when = datetime.strptime(departure['when'], "%Y-%m-%dT%H:%M:%S%z")
               if current_time <= when <= maximum_from_now:
                  return f"Platform {departure['platform']} towards {departure['direction']}"
    return None

def get_prev_and_next_stop(current_stop_id):
    conn = db_connection()
    cursor = conn.cursor()
    
    # Query to find the previous stop ID
    cursor.execute('SELECT stop_id FROM stops WHERE stop_id < ? ORDER BY stop_id DESC LIMIT 1', (current_stop_id,))
    prev_stop_id = cursor.fetchone()
    
    # Query to find the next stop ID
    cursor.execute('SELECT stop_id FROM stops WHERE stop_id > ? ORDER BY stop_id ASC LIMIT 1', (current_stop_id,))
    next_stop_id = cursor.fetchone()
    
    conn.close()
    return prev_stop_id, next_stop_id

def validate_input(updates):
    
    if 'name' in updates and updates['name'] == '' :
        return False, 'Name cannot be blank'
    if 'next_departure' in updates and \
      (updates['next_departure'] == ''):
        return False, 'Next departure cannot be blank'
    
    
    if 'latitude' in updates and not (-90 <= updates['latitude'] <= 90):
        return False, 'Latitude must be between -90 and 90'
    if 'longitude' in updates and not (-180 <= updates['longitude'] <= 180):
        return False, 'Longitude must be between -180 and 180'
    
    
    if 'last_updated' in updates:
        try:
            datetime.strptime(updates['last_updated'], '%Y-%m-%d-%H:%M:%S')
        except ValueError:
            return False, 'Last updated must be in the format yyyy-mm-dd-hh:mm:ss'
    
    return True, ''
def get_departing_info(stop_id):
   url = f'https://v6.db.transport.rest/stops/{stop_id}/departures'
   response = requests.get(url)
   if response.status_code == 200:
      departures = response.json()
      name_list = []
      for departure in departures['departures']:  
         #print(departure)
         current_time = datetime.now(timezone.utc)
         maximum_from_now = current_time + timedelta(minutes=90)
         when = datetime.strptime(departure['when'], "%Y-%m-%dT%H:%M:%S%z")
         if current_time <= when <= maximum_from_now:
            operator_name = departure['line']['operator']['name']
            if operator_name not in name_list:
               name_list.append(operator_name)
            if len(name_list) == 5:
               return name_list
   return name_list

def num_stops_id():
   # 连接到SQLite数据库
   conn = db_connection()
   cursor = conn.cursor()

   # 执行查询
   query = "SELECT COUNT(DISTINCT stop_id) FROM stops"
   cursor.execute(query)

   # 获取查询结果
   count = cursor.fetchone()[0]
   

   # 检查结果
   if count >= 2:
      query_random = "SELECT DISTINCT stop_id FROM stops ORDER BY RANDOM() LIMIT 2"
      cursor.execute(query_random)
      results = cursor.fetchall()
      stop_ids = [item[0] for item in results]
      conn.close()
      return True, stop_ids
   else:
      conn.close()
      return False, None

   

@api.route('/stops')
class StopsList(Resource):
   @api.response(200, "Ok")
   @api.response(201, "Created")
   @api.response(400, "Invalid field in request")
   @api.response(404, "Not found")
   @api.response(503, "Service Unavailable")
   @api.doc(description = "Retrieve a stop")
   @api.expect(parser_query, validate = True)
   def put(self):
      
      query = parser_query.parse_args().get("query")
      url = f'https://v6.db.transport.rest/locations?query={query}&results=5'
      response = requests.get(url)      
      code = response.status_code
      if code == 400:
         return {"message": "Invalid field in request"}, 400
      elif code == 404 or len(response.json()) == 0:
         return {"message": "Not found."}, 404
      elif code == 503:
         return {"message": "Service Unavailable."}, 503
      
      put_list = []
      
        
      for item in response.json():
         put_dict = {}
         stop_id = item["id"]
         last_updated = datetime.now()
         put_dict["stop_id"] = int(stop_id)
         # put_dict["name"] = item["name"]
         name = item["name"]
         put_dict["last_updated"] = last_updated.strftime('%Y-%m-%d-%H:%M:%S')
         # put_dict["latitude"] = item["location"]["latitude"]
         
         # put_dict["longitude"] = item["location"]["longitude"]
         href = f"http://{request.host}/stops/{stop_id}"
         put_dict["_links"] = {"self" : {"href": href}}
         # read => len(res) => >0 => yes => update
         # no => insert
         data = db_read(stop_id)
         print(data)
         if len(data) == 0:
            db_insert(stop_id, put_dict["last_updated"], name, item["location"]["latitude"],  item["location"]["longitude"])
         else:
            db_update(stop_id, put_dict["last_updated"], name, item["location"]["latitude"], item["location"]["longitude"])
         put_list.append(put_dict)
         

      put_list = sorted(put_list, key = lambda x: x['stop_id'])

      return {"message": put_list}, 200
@api.route('/stops/<int:stop_id>')
class stops(Resource):
   @api.response(200, "Ok")
   @api.response(400, "Invalid field in request")
   @api.response(404, "Not found")
   @api.response(503, "Service Unavailable")
   @api.doc(description = "Retrieve a stop")
   @api.expect(parser_query2, validate = True)
   def get(self, stop_id):
      details = db_read(stop_id)
      print(details)
      if len(details) == 0:
         return {"message": "Not found."}, 404
      details = details[0]
      prev_stop_id, next_stop_id = get_prev_and_next_stop(stop_id)
      data = {
         'stop_id': stop_id,
         '_links': {
               'self': {"href": f'http://{request.host}/stops/{stop_id}'}
         }
      }  
      if next_stop_id:
         data['_links']['next'] = {"href": f'http://{request.host}/stops/{next_stop_id[0]}'}
      if prev_stop_id:
         data['_links']['prev'] = {"href": f'http://{request.host}/stops/{prev_stop_id[0]}'}

      fields = parser_query2.parse_args().get("include")
      
      if fields:
         fields = fields.split(',')
      if not fields or 'name' in fields:
         data['name'] = details[2]
      # Add latitude and longitude here similarly
      if not fields or 'last_updated' in fields:
         data['last_updated'] = details[1]
      if not fields or 'latitude' in fields:
         data['latitude'] = details[3]
      # Add latitude and longitude here similarly
      if not fields or 'longitude' in fields:
         data['longitude'] = details[4] 
      if not fields or 'next_departure' in fields:
         data['next_departure'] = get_next_departure(stop_id)
         if not data['next_departure']:
            return {"message": "next_departure Not found."}, 404
      return data, 200
   @api.response(200, "OK")
   @api.response(400, "Invalid field in request")
   @api.response(404, "Not found")
   @api.doc(description = "Delete a stop")
   def delete(self, stop_id):
      data = db_read(stop_id)
      if len(data) == 0:
         return {"message": "The stop_id {} was not found in the database.".format(stop_id), "stop_id": stop_id},404
      else:
         db_delete(stop_id)
         return {"message": "The stop_id {} was removed from the database.".format(stop_id), "stop_id": stop_id},200
   @api.response(200, "Ok")
   @api.response(400, "Invalid field in request")
   @api.response(404, "Not found")
   @api.doc(description = "Update a stop")
   @api.expect(indicator_model, validate=True)
   def patch(self, stop_id):
     
     updates = request.json
     if len(updates) == 0:
        return {"message": "Invalid field in request"}, 400
     details = db_read(stop_id)
     if len(details) == 0:
        return {"message": "Not found."}, 404
     details = details[0]
      
     if 'stop_id' in updates or '_links' in updates:
        return {"message": "Invalid field in request"}, 400
     if 'name' not in updates:
         updates['name'] = details[2]
     if 'last_updated' not in updates:
         updates['last_updated'] = datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
     if 'latitude' not in updates:
         updates['latitude'] = details[3] 
     if 'longitude' not in updates:
         updates['longitude'] = details[4] 

     valid, message = validate_input(updates) 
     if valid:
        db_update(stop_id, updates['last_updated'], updates['name'], updates['latitude'], updates['longitude'])
        return {
               "stop_id": stop_id,
               "last_updated": updates.get('last_updated', datetime.now().strftime('%Y-%m-%d-%H:%M:%S')),
               "_links": {
                  "self": {
                     "href": f"http://{request.host}/stops/{stop_id}"
                  }
               }
         }, 200
     else:
        return {"message": message}, 400                

@api.route('/operator-profiles/<int:stop_id>')
class OperatorProfiles(Resource):
    @api.response(200, "OK")
    @api.response(400, "Bad Request")
    @api.response(404, "Not found")
    @api.response(503, "Service Unavailable")
    @api.doc(description = "Retrieve operator profiles ")
    def get(self, stop_id):
     details = db_read(stop_id)
     if len(details) == 0:
        return {"message": "Not found."}, 404
     details = details[0]
     name = get_departing_info(stop_id)  
     print(name)
     if len(name) == 0:
        return {"message": "Not found."}, 404
      
     profiles = []
     for operator in name:  # 取前5个或全部，哪个少取哪个
        optinfo = gemini.generate_content(f"please tell me about {operator}. Only return the text without newline signal").text
        optinfo = optinfo.replace('\n', '')
        profiles.append({
               "operator_name": operator,
               "information": optinfo
         })
      
     return {
         "stop_id": stop_id,
         "profiles": profiles
      }, 200

@api.route('/guide')
class TourismGuide(Resource):
    @api.response(200, "OK")
    @api.response(400, "Bad Request")
    @api.response(503, "Service Unavailable")
    @api.doc(description = "Create a tourism guide")
    def get(self):
     
      # 检查数据库中是否有足够的停靠站
     vaild, stop_ids = num_stops_id()
     if not vaild:
        return {"message": "Bad Request"}, 400
   #   print(stop_ids)
   
     source_stop_id = stop_ids[0]
     destination_stop_id = stop_ids[1]
     
     data_source = db_read(source_stop_id) 
     data_source = data_source[0]
     data_destination = db_read(destination_stop_id) 
     data_destination = data_destination[0]
     data_source_name = data_source[2]
     data_destination_name = data_destination[2]
   #   print(data_source_name)  
   #   print(data_destination_name)
     info = gemini.generate_content(f"I need a tourist explore guidence. I will tell you source place and destination place. The guidence should includes substantial information about at least one point of interest at the source. The guidence should also includes substantial information about at least one point of interest at the destination and includes other substantial information to enhance a tourist's experience using the guide.Please tell me the tour plan and POI details. The source is {data_source_name}, destination pa is {data_destination_name}").text
     info = info.replace('\n', '')
     print(info)

        # 创建 TXT 文件并返回
     with open(txt_file, 'w') as f:
         print(info, file = f)
        
     return send_file(txt_file, as_attachment=True, attachment_filename=txt_file),200

if __name__ == "__main__":
    # Here's a quick example of using the Generative AI API:
   app.run(debug=True)
   
   question = "Give me some facts about UNSW!"
   response = gemini.generate_content(question)
   print(question)
   print(response.text)

