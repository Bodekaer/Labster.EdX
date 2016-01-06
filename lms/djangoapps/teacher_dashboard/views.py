import requests
import logging
import urlparse

from django.http import HttpResponse
from opaque_keys.edx.locations import SlashSeparatedCourseKey
from django.conf import settings
from django.contrib.auth.decorators import login_required

from courseware.courses import get_course_by_id
from edxmako.shortcuts import render_to_response
from xmodule.modulestore.django import modulestore

from teacher_dashboard.utils import _send_request

log = logging.getLogger(__name__)


@login_required
def dashboard_view(request, course_id):
    """
    Teacher dashboard renders data using backbone from /static/teacher_dashboard/js
    """
    # Course is needed for display others tabs
    course_key = SlashSeparatedCourseKey.from_deprecated_string(course_id)
    with modulestore().bulk_operations(course_key):
        course = get_course_by_id(course_key, depth=2)
    context = {
        'course': course,
    }
    return render_to_response('teacher_dashboard/dashboard.html', context)


def licenses_api_call(request):
    """
    Redirect Api call to Labster API
    """
    url = urlparse.urljoin(settings.LABSTER_API_URL, settings.LABSTER_ENDPOINTS.get('licenses'))
    response = _send_request(url=url, data={'email': request.user.email})
    return HttpResponse(response, content_type="application/json")


def simulations_api_call(request, license_pk):
    url = urlparse.urljoin(settings.LABSTER_API_URL, settings.LABSTER_ENDPOINTS.get('simulations').format(license_pk))
    response = _send_request(url=url, data=None)
    return HttpResponse(response, content_type="application/json")


def students_api_call(request, license_pk, simulation_pk):
    url = urlparse.urljoin(settings.LABSTER_API_URL,
                           settings.LABSTER_ENDPOINTS.get('students').format(license_pk, simulation_pk))
    response = _send_request(url=url, data=None)
    return HttpResponse(response, content_type="application/json")
