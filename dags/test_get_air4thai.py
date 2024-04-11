import logging
import re
import os
import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator
from airflow.utils import timezone
import pendulum

import requests
import json

def _get_data_api():
    url = "http://air4thai.pcd.go.th/services/getNewAQI_JSON.php"

    response = requests.get(url)

    data = eval(response.text)
   
    # Get the current datetime in the local time zone
    current_datetime = pendulum.now("Asia/Bangkok")

    # Format the datetime
    f_datetime = current_datetime.strftime("%Y_%m_%d_%H00")

    # Define the filename using the formatted date and time
    filename = f"data_air_{f_datetime}.json"
    logging.info(f"**** filename : {filename}")
    
    # Write the data to the JSON file
    with open(f"/opt/airflow/dags/data_air4thai.json", 'w') as file:
        json.dump(data, file)

    logging.info(f"JSON data saved to /opt/airflow/dags/data_air4thai.json")

    # Local file path
    local_file_path = f"/opt/airflow/dags/data_air4thai.json"
    logging.info('local file path : ' + local_file_path)

    # Destination bucket and object in GCS
    gcs_bucket = "ds525-capstone-test-49"
    logging.info('bucket name : ' + gcs_bucket)

    gcs_object = f"data_raw_air/{filename}"  # Specify the desired object name here
    logging.info('dst : ' + gcs_object)

    # # Create a LocalFilesystemToGCSOperator to upload the file to GCS
    upload_task = LocalFilesystemToGCSOperator(
        task_id="upload_file_to_gcs",
        src=local_file_path,
        dst=gcs_object,
        bucket=gcs_bucket,
        gcp_conn_id="my_gcp_conn",
       
    )
    upload_task.execute(context=None)

    # Move the local file after uploading it to GCS
    # os.remove(local_file_path)


with DAG (
    "test_get_air4thai",
    start_date=timezone.datetime(2024, 4, 2),
    schedule="15 * * * *", #cron expression
    tags=["DS525 Capstone"],
):

    get_data_api = PythonOperator(
        task_id="get_data_api",
        python_callable=_get_data_api,
    )

    # Set task dependencies
    get_data_api