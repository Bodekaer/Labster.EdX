"""
Region module.
Can contain region specific logic or functionality.
"""
from django.conf import settings
from openedx.core.djangoapps.site_configuration import helpers as configuration_helpers


class Region(object):
    """
    Represents region created from loaded params.
    """
    def __init__(self, request):
        regions = configuration_helpers.get_value('REGIONS', settings.REGIONS)
        # List of country codes: https://dev.maxmind.com/geoip/legacy/codes/iso3166/
        current_region = request.session.get('country_code')
        params = regions[current_region] if current_region in regions.keys() else {}
        for key, val in params.items():
            setattr(self, key, val)
