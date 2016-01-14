import requests
import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext as _

log = logging.getLogger(__name__)


class LabsterApiError(Exception):
    """
    This exception is raised in the case where problems with Labster API appear.
    """
    pass


def _send_request(url, method=None, data=None):
    """
    Sends a request the Labster API. 3ae623019d6c2ce7add94eb54b4690463040cca6
    """

    headers = {
        "authorization": 'Token {}'.format(settings.LABSTER_API_AUTH_TOKEN),
        "content-type": 'application/json',
        "accept": 'application/json',
    }
    try:
        if method == 'POST':
            response = requests.request(method=method, url=url, headers=headers, data=data)
        else:
            response = requests.get(url, headers=headers, params=data)
        response.raise_for_status()
        return response.content

    except (requests.exceptions.InvalidSchema, requests.exceptions.InvalidURL, requests.exceptions.MissingSchema) as ex:
        log.exception("Setup Labster endpoints in settings: \n%r", ex)
        raise ImproperlyConfigured(_("Setup Labster endpoints in settings"))

    except requests.RequestException as ex:
        log.exception("Labster API is unavailable:\n%r", ex)
        raise LabsterApiError(_("Labster API is unavailable."))

    except ValueError as ex:
        log.error("Invalid JSON:\n%r", ex)
