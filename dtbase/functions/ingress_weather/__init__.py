from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from azure.functions import HttpRequest, HttpResponse

from dtbase.ingress.ingress_weather import OpenWeatherDataIngress


def parse_datetime_argument(dt_str: str) -> str | dt.datetime:
    """Parse datetime argument from HTTP request.

    Return either a datetime object or the string "present".
    """
    if dt_str == "present":
        return dt_str

    now = dt.datetime.now()
    tolerance = dt.timedelta(seconds=10)
    datetime = dt.datetime.fromisoformat(dt_str)
    if now - tolerance <= datetime <= now + tolerance:
        return "present"
    return datetime


def main(req: HttpRequest) -> HttpResponse:
    logging.info("Starting Open Weather Map ingress function.")

    req_body = req.get_json()
    params: dict[str, Any] = {}
    for parameter_name in {
        "from_dt",
        "to_dt",
        "api_key",
        "latitude",
        "longitude",
    }:
        parameter = req_body.get(parameter_name)
        if parameter is None:
            return HttpResponse(
                f"Must provide {parameter_name} in request body.", status_code=400
            )
        params[parameter_name] = parameter

    try:
        params["from_dt"] = parse_datetime_argument(params["from_dt"])
        params["to_dt"] = parse_datetime_argument(params["to_dt"])
    except ValueError:
        return HttpResponse(
            "from_dt and to_dt must be ISO 8601 datetime strings or 'present'.",
            status_code=400,
        )

    weather_ingress = OpenWeatherDataIngress()
    weather_ingress.ingress_data(**params)

    logging.info("Finished Open Weather Map Ingress.")
    return HttpResponse("Successfully ingressed weather data.", status_code=200)
