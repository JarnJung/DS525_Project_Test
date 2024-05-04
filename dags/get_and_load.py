import logging
import re
import os
import datetime
import pytz
import csv

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.transfers.local_to_gcs import LocalFilesystemToGCSOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator

from airflow.utils import timezone
import pendulum
from google.cloud import bigquery
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

    gcs_object = f"stay/{filename}"  # Specify the desired object name here
    logging.info('dst : ' + gcs_object)

    return local_file_path, gcs_object, gcs_bucket


def _upload_to_gcs(local_file_path, gcs_object):
    # Create a LocalFilesystemToGCSOperator to upload the file to GCS
    upload_task = LocalFilesystemToGCSOperator(
        task_id="upload_file_to_gcs",
        src=local_file_path,
        dst=gcs_object,
        bucket="ds525-capstone-test-49",
        gcp_conn_id="my_gcp_conn",
    )
    upload_task.execute(context=None)

def _extract_data_to_csv(local_file_path):
    csv_output = f"/opt/airflow/dags/data_to_load.csv"

    with open(csv_output, "w", newline='') as csv_file:
        writer = csv.writer(csv_file)
        
        header = ['station_id', 'date', 'time', 'aqi_val', 'aqi_color_id', 
             'co_val', 'co_color_id', 'no2_val', 'no2_color_id', 
             'o3_val', 'o3_color_id', 'pm10_val', 'pm10_color_id',
             'pm25_val', 'pm25_color_id', 'so2_val', 'so2_color_id']
        
        # Write header
        writer.writerow(header)

        with open(local_file_path, "r") as f:
            data = json.load(f)

            for each in data['stations']:
                station_id = each['stationID']
                date = each['AQILast']['date']
                time = each['AQILast']['time']
                aqi = max(0, float(each['AQILast']['AQI']['aqi']))
                aqi_color_id = max(0, int(each['AQILast']['AQI']['color_id']))
                co_value = max(0, float(each['AQILast']['CO']['value']))
                co_color_id = max(0, int(each['AQILast']['CO']['color_id']))
                no2_value = max(0, float(each['AQILast']['NO2']['value']))
                no2_color_id = max(0, int(each['AQILast']['NO2']['color_id']))
                o3_value = max(0, float(each['AQILast']['O3']['value']))
                o3_color_id = max(0, int(each['AQILast']['O3']['color_id']))
                pm10_value = max(0, float(each['AQILast']['PM10']['value']))
                pm10_color_id = max(0, int(each['AQILast']['PM10']['color_id']))
                pm25_value = max(0, float(each['AQILast']['PM25']['value']))
                pm25_color_id = max(0, int(each['AQILast']['PM25']['color_id']))
                so2_value = max(0, float(each['AQILast']['SO2']['value']))
                so2_color_id = max(0, int(each['AQILast']['SO2']['color_id']))

                val = [station_id ,
                        date , time ,
                    aqi, aqi_color_id,
                    co_value,  co_color_id,
                    no2_value, no2_color_id,
                    o3_value, o3_color_id,
                    pm10_value, pm10_color_id,
                    pm25_value, pm25_color_id,
                    so2_value, so2_color_id,]

                writer.writerow(val)

    return csv_output

def _upload_csv_to_gcs(csv_output, gcs_bucket):
    # Create a LocalFilesystemToGCSOperator to upload the file to GCS
    gcs_csv_object = "staging/data_to_load.csv"  # Specify the desired object name here
    logging.info('csv dst : ' + gcs_csv_object)

    logging.info('csv out : ' + csv_output)

    upload_task = LocalFilesystemToGCSOperator(
        task_id="upload_csv_to_gcs",
        src=csv_output,
        dst=gcs_csv_object,
        bucket= gcs_bucket,
        gcp_conn_id="my_gcp_conn",
    )
    upload_task.execute(context=None)   

    return gcs_bucket, gcs_csv_object


with DAG (
    "load_data_to_bq",
    start_date=timezone.datetime(2024, 5, 1, 14, 0, 0, tzinfo=pytz.UTC),
    schedule_interval="20 * * * *", #cron expression
    tags=["DS525 Capstone"],
) as dag:

    get_data_api = PythonOperator(
        task_id="get_data_api",
        python_callable=_get_data_api,
    )

    upload_to_gcs = PythonOperator(
        task_id="upload_to_gcs",
        python_callable=_upload_to_gcs,
        op_kwargs={"local_file_path": "{{ task_instance.xcom_pull(task_ids='get_data_api')[0] }}",
                   "gcs_object": "{{ task_instance.xcom_pull(task_ids='get_data_api')[1] }}"},
    )

    extract_data= PythonOperator(
        task_id="extract_data",
        python_callable=_extract_data_to_csv,
        op_kwargs={"local_file_path": "{{ task_instance.xcom_pull(task_ids='get_data_api')[0] }}",},
    )

    upload_csv_to_gcs = PythonOperator(
        task_id="upload_csv_to_gcs",
        python_callable=_upload_csv_to_gcs,
        op_kwargs={"csv_output": "{{ task_instance.xcom_pull(task_ids='extract_data') }}",
                   "gcs_bucket": "{{ task_instance.xcom_pull(task_ids='get_data_api')[2] }}"},
    )

    load_data_to_bq = GCSToBigQueryOperator(
        task_id="load_data_to_bq",
        source_objects=["{{task_instance.xcom_pull(task_ids='upload_csv_to_gcs')[1] }}"],
        bucket="{{ task_instance.xcom_pull(task_ids='get_data_api')[2] }}",
        destination_project_dataset_table="ds525-capstone.ds525_capstone_db.aqi_data_test",
        source_format="CSV",
        skip_leading_rows=1,
        schema_fields=[
            {"name": "station_id", "type": "STRING"},
            {"name": "date", "type": "STRING"},
            {"name": "time", "type": "STRING"},
            {"name": "aqi_val", "type": "FLOAT64"},
            {"name": "aqi_color_id", "type": "INT64"},
            {"name": "co_val", "type": "FLOAT64"},
            {"name": "co_color_id", "type": "INT64"},
            {"name": "no2_val", "type": "FLOAT64"},
            {"name": "no2_color_id", "type": "INT64"},
            {"name": "o3_val", "type": "FLOAT64"},
            {"name": "o3_color_id", "type": "INT64"},
            {"name": "pm10_val", "type": "FLOAT64"},
            {"name": "pm10_color_id", "type": "INT64"},
            {"name": "pm25_val", "type": "FLOAT64"},
            {"name": "pm25_color_id", "type": "INT64"},
            {"name": "so2_val", "type": "FLOAT64"},
            {"name": "so2_color_id", "type": "INT64"}
        ],
        autodetect=True,  # Set autodetect to False since the schema is predefined        
        write_disposition="WRITE_APPEND",
        gcp_conn_id="my_gcp_conn",
    )


    get_data_api >> upload_to_gcs >> extract_data >> upload_csv_to_gcs >> load_data_to_bq 