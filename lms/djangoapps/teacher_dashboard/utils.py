import json
import requests
import logging

from requests import RequestException
from django.conf import settings

from labster_course_license.views import LabsterApiError

log = logging.getLogger(__name__)


def _send_request(url, data=None):
    """
    Sends a request the Labster API.
    """
    headers = {
        "authorization": 'Token {}'.format(settings.LABSTER_API_AUTH_TOKEN),
        "content-type": 'application/json',
        "accept": 'application/json',
    }
    try:
        response = requests.get(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        return response.content
    except RequestException as ex:
        log.exception("Labster API is unavailable:\n%r", ex)
        raise LabsterApiError(_("Labster API is unavailable."))
    except ValueError as ex:
        log.error("Invalid JSON:\n%r", ex)
