"""
Region module.
Can contain region specific logic or functionality.
"""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


class Region(object):
    """
    Represents region created from loaded params.
    """
    def __init__(self, request):
        regions = configuration_helpers.get_value('REGIONS', settings.REGIONS)
        # List of country codes: https://dev.maxmind.com/geoip/legacy/codes/iso3166/
        country_code = request.session.get('country_code')
        current_region = country_code
        if current_region in regions.keys():
            params = regions[current_region]
            for key, val in params.items():
                setattr(self, key, val)
        else:
            raise ImproperlyConfigured(
                "Region object can not be created from country code `%s`" % country_code
            )
