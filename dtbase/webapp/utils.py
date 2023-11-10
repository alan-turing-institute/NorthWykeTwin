"""Utilities for the front end."""
import datetime as dt
import unicodedata
import urllib
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from flask import Request, Response

from dtbase.core.constants import CONST_BACKEND_URL as BACKEND_URL


def parse_rfc1123_datetime(string: str) -> dt.datetime:
    """Parse an RFC 1123 formatted datetime string into a datetime object.

    The backend returns this format, it's a web standard.
    """
    return dt.datetime.strptime(string, "%a, %d %b %Y %H:%M:%S GMT")


def parse_url_parameter(request: Request, parameter: str) -> Optional[str]:
    """Parse a URL parameter, doing any unquoting as necessary. Return None if the
    parameter doesn't exist.
    """
    raw = request.args.get(parameter)
    if raw is not None:
        parsed = urllib.parse.unquote(raw)
    else:
        parsed = None
    return parsed


def backend_call(
    request_type: str,
    end_point_path: str,
    payload: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> Response:
    """Make an API call to the backend server."""
    headers = {} if headers is None else headers
    request_func = getattr(requests, request_type)
    url = f"{BACKEND_URL}{end_point_path}"
    if payload:
        headers = headers | {"content-type": "application/json"}
        response = request_func(url, headers=headers, json=payload)
    else:
        response = request_func(url)
    return response


def convert_form_values(
    variables: List[Dict[str, Any]], form: dict, prefix: str = "identifier"
) -> Dict[str, Any]:
    """
    Prepared the form and converts values to their respective datatypes as defined in
    the schema. Returns a dictionary of converted values.
    """

    # Define a dictionary mapping type names to conversion functions
    conversion_functions = {
        "integer": int,
        "float": float,
        "string": str,
        "boolean": lambda x: x.lower() == "true",
    }

    converted_values = {}

    for variable in variables:
        value = form.get(f"{prefix}_{variable['name']}")
        datatype = variable["datatype"]

        # Get the conversion function for this datatype
        conversion_function = conversion_functions.get(datatype)

        if not conversion_function:
            raise ValueError(
                f"Unknown datatype '{datatype}' for variable '{variable['name']}'"
            )

        try:
            # Convert the value to the correct datatype
            converted_value = conversion_function(value)
        except ValueError:
            raise ValueError(
                f"Invalid value '{value}' for variable '{variable['name']}' "
                f"(expected {datatype})"
            )

        converted_values[variable["name"]] = converted_value

    return converted_values


# The following two functions mimic similar ones from Django.


def url_has_allowed_host_and_scheme(url, allowed_hosts, require_https=False):
    """
    Return `True` if the url uses an allowed host and a safe scheme.

    Always return `False` on an empty url.

    If `require_https` is `True`, only 'https' will be considered a valid scheme, as
    opposed to 'http' and 'https' with the default, `False`.
    """
    if url is not None:
        url = url.strip()
    if not url:
        return False
    if allowed_hosts is None:
        allowed_hosts = set()
    elif isinstance(allowed_hosts, str):
        allowed_hosts = {allowed_hosts}
    # Chrome treats \ completely as / in paths but it could be part of some
    # basic auth credentials so we need to check both URLs.
    return _url_has_allowed_host_and_scheme(
        url, allowed_hosts, require_https=require_https
    ) and _url_has_allowed_host_and_scheme(
        url.replace("\\", "/"), allowed_hosts, require_https=require_https
    )


def _url_has_allowed_host_and_scheme(url, allowed_hosts, require_https=False):
    # Chrome considers any URL with more than two slashes to be absolute, but
    # urlparse is not so flexible. Treat any url with three slashes as unsafe.
    if url.startswith("///"):
        return False
    try:
        url_info = urlparse(url)
    except ValueError:  # e.g. invalid IPv6 addresses
        return False
    # Forbid URLs like http:///example.com - with a scheme, but without a hostname.
    # In that URL, example.com is not the hostname but, a path component. However,
    # Chrome will still consider example.com to be the hostname, so we must not
    # allow this syntax.
    if not url_info.netloc and url_info.scheme:
        return False
    # Forbid URLs that start with control characters. Some browsers (like
    # Chrome) ignore quite a few control characters at the start of a
    # URL and might consider the URL as scheme relative.
    if unicodedata.category(url[0])[0] == "C":
        return False
    scheme = url_info.scheme
    # Consider URLs without a scheme (e.g. //example.com/p) to be http.
    if not url_info.scheme and url_info.netloc:
        scheme = "http"
    valid_schemes = ["https"] if require_https else ["http", "https"]
    return (not url_info.netloc or url_info.netloc in allowed_hosts) and (
        not scheme or scheme in valid_schemes
    )
