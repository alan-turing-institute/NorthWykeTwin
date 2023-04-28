"""
A module for the main dashboard actions
"""
import datetime as dt
import json
import re

from flask import render_template, request
from flask_login import login_required
import pandas as pd

from app.sensors import blueprint
import utils


def fetch_all_sensor_types():
    """Get all sensor types from the database.
    Args:
        None
    Returns:
        List of dictionaries, one for each sensor type
    """
    response = utils.backend_call("get", "/sensor/list_sensor_types")
    if response.status_code != 200:
        # TODO Write a more useful reaction to this.
        raise RuntimeError(f"A backend call failed: {response}")
    sensor_types = response.json()
    return sensor_types


def fetch_all_sensors(sensor_type):
    """Get all sensors of a given sensor type from the database.
    Args:
        sensor_type: The name of the sensor type.
    Returns:
        List of dictionaries, one for each sensor.
    """
    response = utils.backend_call("get", f"/sensor/list/{sensor_type}")
    if response.status_code != 200:
        # TODO Write a more useful reaction to this.
        raise RuntimeError(f"A backend call failed: {response}")
    sensors = response.json()
    return sensors


def fetch_sensor_data(dt_from, dt_to, measures, sensor_ids):
    """Get the data from a given sensor and measure, in a given time period.
    Args:
        dt_from: Datetime from
        dt_to: Datetime to
        measures: List of measures to get
        sensor_ids: Unique IDs of sensors to get data for
    Returns:
        Dictionary with keys being sensor IDs and values being pandas DataFrames of
        data, with columns for each measure and for timestamp.
    """
    result = {}
    for sensor_id in sensor_ids:
        measure_readings_list = []
        for measure in measures:
            payload = {
                "dt_from": dt_from.isoformat(),
                "dt_to": dt_to.isoformat(),
                "measure_name": measure["name"],
                "sensor_uniq_id": sensor_id,
            }
            response = utils.backend_call("get", "/sensor/sensor_readings", payload)
            if response.status_code != 200:
                # TODO Write a more useful reaction to this.
                raise RuntimeError(f"A backend call failed: {response}")
            readings = response.json()
            index = [x["timestamp"] for x in readings]
            values = [x["value"] for x in readings]
            index = list(map(utils.parse_rfc1123_datetime, index))
            series = pd.Series(data=values, index=index, name=measure["name"])
            measure_readings_list.append(series)
        df = pd.concat(measure_readings_list, axis=1)
        df = df.sort_index().reset_index(names="timestamp")
        result[sensor_id] = df
    return result


@blueprint.route("/index")
@login_required
def index():
    """Index page."""
    # Parse the various parameters we may have been passed, and load some generally
    # necessary data like list of all sensors and sensor types.
    dt_from = utils.parse_url_parameter(request, "startDate")
    dt_to = utils.parse_url_parameter(request, "endDate")
    sensor_ids = utils.parse_url_parameter(request, "sensorIds")
    if sensor_ids is not None:
        # sensor_ids is passed as a comma-separated (or semicolon, although those aren't
        # currently used) string, split it into a list of ids.
        sensor_ids = tuple(re.split(r"[;,]+", sensor_ids.rstrip(",;")))

    sensor_types = fetch_all_sensor_types()
    sensor_type_name = utils.parse_url_parameter(request, "sensorType")
    if sensor_types:
        if sensor_type_name is None:
            # By default, just pick the first sensor type in the list.
            sensor_type_name = sensor_types[0]["name"]
    else:
        sensor_type_name = None
    all_sensors = fetch_all_sensors(sensor_type_name)

    # If we don't have the information necessary to plot data for sensors, just render
    # the selector version of the page.
    is_valid_sensor_type = sensor_type_name is not None and sensor_type_name in [
        s["name"] for s in sensor_types
    ]
    if (
        dt_from is None
        or dt_to is None
        or sensor_ids is None
        or not is_valid_sensor_type
    ):
        today = dt.datetime.today()
        dt_from = today - dt.timedelta(days=7)
        dt_to = today
        return render_template(
            "sensors.html",
            sensor_type=sensor_type_name,
            sensor_types=sensor_types,
            all_sensors=all_sensors,
            sensor_ids=sensor_ids,
            dt_from=dt_from,
            dt_to=dt_to,
            data=dict(),
            measures=[],
        )

    # Convert datetime strings to objects and make dt_to run to the end of the day in
    # question.
    dt_from = dt.datetime.fromisoformat(dt_from)
    dt_to = (
        dt.datetime.fromisoformat(dt_to)
        + dt.timedelta(days=1)
        + dt.timedelta(milliseconds=-1)
    )

    # Get all the sensor measures for this sensor type.
    measures = next(
        s["measures"] for s in sensor_types if s["name"] == sensor_type_name
    )
    sensor_data = fetch_sensor_data(dt_from, dt_to, measures, sensor_ids)

    # Convert the sensor data to an easily digestible version for Jinja.
    # You may wonder, why we first to_json, and then json.loads. That's just to have
    # the data in a nice nested dictionary that a final json.dumps can deal with.
    data_dict = {
        k: json.loads(v.to_json(orient="records", date_format="iso"))
        for k, v in sensor_data.items()
    }
    return render_template(
        "sensors.html",
        sensor_type=sensor_type_name,
        sensor_types=sensor_types,
        all_sensors=all_sensors,
        sensor_ids=sensor_ids,
        dt_from=dt_from,
        dt_to=dt_to,
        data=data_dict,
        measures=measures,
    )