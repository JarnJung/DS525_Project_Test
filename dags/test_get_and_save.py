import logging
import re
import datetime

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.utils import timezone

import requests
import json

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
    filename = f"/opt/airflow/dags/data_{file_string}.json"

    # Write the data to the JSON file
    with open(filename, 'w') as file:
        json.dump(data, file)

    logging.info(f"JSON data saved to {filename}")

with DAG(
    "test_get_and_save",
    start_date=timezone.datetime(2024, 3, 25),
    schedule=None, #cron expression
    tags=["DS525 Capstone"],
):
    start = EmptyOperator(task_id="start")

    get_data__api = PythonOperator(
        task_id="get_data_api",
        python_callable=_get_data_api,
    )

    end = EmptyOperator(task_id="end")

    start >> get_data__api >> end