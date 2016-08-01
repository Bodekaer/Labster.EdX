"""
Voucher views.
"""
import logging

import requests
from requests.exceptions import RequestException
from django.contrib import messages
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.conf import settings
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_http_methods

from edxmako.shortcuts import render_to_response
from enrollment.api import add_enrollment
from enrollment.errors import (
    CourseNotFoundError, CourseEnrollmentError,
    CourseModeNotFoundError, CourseEnrollmentExistsError
)
from labster_course_license.models import CourseLicense
from labster_vouchers import forms


log = logging.getLogger(__name__)


@require_http_methods(["GET"])
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@login_required
def enter_voucher(request):
    """
    Enter Voucher View.
    """
    context = {'user': request.user}
    return render_to_response('labster/enter_voucher.html', context)


@require_http_methods(["POST"])
@ensure_csrf_cookie
@login_required
def activate_voucher(request):
    """
    Gets license code from API, fetches related course_id and enrolls student.
    """
    form = forms.ValidationForm(request.POST)
    enter_voucher_url = reverse('enter_voucher')

    if not form.is_valid():
        messages.error(request, "Enter a valid voucher code.")
        return redirect(enter_voucher_url)

    code = form.cleaned_data['code']
    url = settings.LABSTER_ENDPOINTS.get('voucher_license').format(code=code)

    # Send voucher code to API and get license back
    headers = {
        "authorization": 'Token {}'.format(settings.LABSTER_API_AUTH_TOKEN),
        "accept": 'application/json',
    }
    response = None

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        license_code = response.json()['license']
    except (RequestException, KeyError, ValueError) as ex:
        if getattr(response, 'status_code', None) == 404:
            messages.error(request, _(
                "Cannot find a voucher '{}'. Please contact Labster support team."
            ).format(code))
            redirect(enter_voucher_url)
        else:
            log.exception("Labster API is unavailable:\n%r", ex)
            messages.error(request, _(
                "There are some issues with applying your voucher. Please try again in a few minutes."
            ))
            redirect(enter_voucher_url)

    course_licenses = CourseLicense.objects.filter(license_code=license_code)

    if not course_licenses:
        messages.error(
            request,
            _(
                "Cannot find a course for the voucher '{}'."
                "Please contact Labster support team."
            ).format(code)
        )
        redirect(enter_voucher_url)

    for course_license in course_licenses:
        course_id = unicode(course_license.course_id)
        try:
            # enroll student to course
            add_enrollment(request.user, course_id)
        except CourseNotFoundError:
            messages.error(
                request,
                _(u"No course '{course_id}' found for enrollment").format(course_id=course_id)
            )
            return redirect(enter_voucher_url)
        except CourseEnrollmentExistsError:
            messages.error(
                request,
                _(u"You have been already enrolled to the course '{course_id}'.").format(course_id=course_id)
            )
            return redirect(enter_voucher_url)
        except CourseEnrollmentError:
            messages.error(
                request,
                _(
                    u"An error occurred while creating the new course enrollment for user "
                    u"'{username}' in course '{course_id}'"
                ).format(username=request.user.username, course_id=course_id)
            )
            return redirect(enter_voucher_url)

    return redirect(reverse('dashboard'))
