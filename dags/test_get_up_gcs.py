import logging
import re
import datetime

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator
from airflow.utils import timezone
import os

import requests
import json

# Local file path
filename = ""
local_file_path = ""

# Destination bucket and object in GCS
gcs_bucket = "ds525-capstone-test-49"
gcs_object = ""  # Specify the desired object name here


def _get_data_api():
    url = "https://data.tmd.go.th/api/Weather3Hours/V2/?uid=api&ukey=api12345&format=json"

    response = requests.get(url)

    buffer_data = response.text
    buffer_data = buffer_data.replace('{"@attributes":{"Unit":"degree"},"0":"   "}','"0"')
    buffer_data = buffer_data.replace('{"@attributes":{"Unit":"km"}}','"0"')
    buffer_data = buffer_data.replace('\/','/')
    data = eval(buffer_data)

    date_time = data['Header']['LastBuildDate']

    # Use regex to find the position of the colon
    match = re.search(':', date_time)

    if match:
        # Cut the string before the colon
        modified_string = date_time[:match.start()]

    #     print(modified_string)  # Output: 2024-03-25 22
    else:
        logging.info("Colon not found in the string.")
        
    # Replace both space and colon with an empty string
    file_string = (modified_string.replace(' ', '-').replace('-', '_')) + '00'

    #logging.info(file_string)

    # Define the filename using the formatted date and time
    filename = f"data_{file_string}.json"

    # Write the data to the JSON file
    with open(f"/opt/airflow/dags/{filename}", 'w') as file:
        json.dump(data, file)

    logging.info(f"JSON data saved to /opt/airflow/dags/{filename}")

    # Local file path
    local_file_path = f"/opt/airflow/dags/{filename}"
    logging.info('local file path : ' + local_file_path)

    # Destination bucket and object in GCS
    gcs_bucket = "ds525-capstone-test-49"
    logging.info('bucket name : ' + gcs_bucket)

    gcs_object = f"data/{filename}"  # Specify the desired object name here
    logging.info('dst : ' + gcs_object)

    # Create a LocalFilesystemToGCSOperator to upload the file to GCS
    upload_task = LocalFilesystemToGCSOperator(
        task_id="upload_file_to_gcs",
        src=local_file_path,
        dst=gcs_object,
        bucket=gcs_bucket,
        gcp_conn_id="my_gcp_conn",
       
    )
    upload_task.execute(context=None)

    # Move the local file after uploading it to GCS
    os.remove(local_file_path)
    
with DAG(
    "test_get_up_gcs",
    start_date=timezone.datetime(2024, 3, 25),
    schedule="15 1,4,7,10,13,16,19,22 * * *", #cron expression
    tags=["DS525 Capstone"],
):
    get_data__api = PythonOperator(
        task_id="get_data_api",
        python_callable=_get_data_api,
    )   
    

    # Set task dependencies
    get_data__api