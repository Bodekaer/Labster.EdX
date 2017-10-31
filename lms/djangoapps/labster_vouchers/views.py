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
from django.http import Http404

from edxmako.shortcuts import render_to_response
from enrollment.api import add_enrollment
from openedx.core.lib.exceptions import CourseNotFoundError
from enrollment.errors import (
    CourseEnrollmentError, CourseEnrollmentExistsError
)
from labster_course_license.models import CourseLicense
from labster_vouchers import forms
from student.models import anonymous_id_for_user
from xmodule.modulestore.django import modulestore


log = logging.getLogger(__name__)


class ItemNotFoundError(Exception):
    """
    This exception is raised in the case where items is not found in Labster API.
    """
    pass


class LabsterApiError(Exception):
    """
    This exception is raised in the case where problems with Labster API appear.
    """
    pass


class VoucherError(Exception):
    """
    This exception is raised in the case where problems with vouchers appear.
    """
    pass


@require_http_methods(["GET"])
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@login_required
def enter_voucher(request):
    """
    Enter Access Code View.
    """
    if not getattr(settings, 'LABSTER_FEATURES', {}).get('ENABLE_VOUCHERS'):
        raise Http404

    context = {'user': request.user}
    return render_to_response('labster/enter_voucher.html', context)


def activate_voucher(voucher, user_id, email, context_id):
    """
    Activates the voucher.
    """
    url = settings.LABSTER_ENDPOINTS.get('voucher_activate')
    headers = {
        "authorization": 'Token {}'.format(settings.LABSTER_API_AUTH_TOKEN),
        "accept": 'application/json',
    }

    data = {
        'user_id': user_id,
        'email': email,
        'context_id': context_id,
        'voucher': voucher,
    }

    response = None
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
    except RequestException as ex:
        if getattr(response, 'status_code', None) == 404:
            raise ItemNotFoundError
        else:
            msg = (
                "Issues with access code activation: user_id='%s', email='%s', "
                "context_id='%s', voucher='%s',\nerror:\n%r"
            )
            log.exception(msg, user_id, email, context_id, voucher, ex)
            raise LabsterApiError(_("Labster API is unavailable."))


@require_http_methods(["POST"])
@ensure_csrf_cookie
@login_required
def activate_voucher_view(request):
    """
    Gets license code from API, fetches related course_id and enrolls student.
    """
    if not getattr(settings, 'LABSTER_FEATURES', {}).get('ENABLE_VOUCHERS'):
        raise Http404

    enter_voucher_url = reverse('enter_voucher')

    if not request.user.is_active:
        messages.error(request, _(
            "Access Code cannot be applied, because your account has not been activated yet."
        ))
        return redirect(enter_voucher_url)

    form = forms.ValidationForm(request.POST)

    if not form.is_valid():
        messages.error(request, _("Please enter a valid access code."))
        return redirect(enter_voucher_url)

    code = form.cleaned_data['code']

    try:
        license_code = get_license(code)
    except VoucherError as ex:
        messages.error(request, unicode(ex))
        return redirect(enter_voucher_url)
    except ItemNotFoundError:
        messages.error(request, _(
            "Cannot find an access code '{}'. Please contact Labster support team."
        ).format(code))
        return redirect(enter_voucher_url)
    except LabsterApiError:
        messages.error(request, _(
            "There are some issues with applying your access code. Please try again in a few minutes."
        ))
        return redirect(enter_voucher_url)

    course_licenses = CourseLicense.objects.filter(license_code=license_code)

    if not course_licenses:
        messages.error(
            request,
            _("Cannot find a course for provided access code '{}'. Please contact Labster support team.").format(code)
        )
        return redirect(enter_voucher_url)

    course_license = course_licenses[0]
    course_id = course_license.course_id
    anon_uid = anonymous_id_for_user(request.user, course_id)
    context_id = course_id.to_deprecated_string()

    try:
        activate_voucher(code, anon_uid, request.user.email, context_id)
    except ItemNotFoundError:
        messages.error(request, _(
            "Cannot find an access code '{}'. Please contact Labster support team."
        ).format(code))
        return redirect(enter_voucher_url)
    except LabsterApiError:
        messages.error(request, _(
            "There are some issues with applying your access code. Please try again in a few minutes."
        ))
        return redirect(enter_voucher_url)

    try:
        # enroll student to course
        add_enrollment(request.user, unicode(course_id))
    except CourseNotFoundError:
        messages.error(request, _(u"No course found for enrollment."))
        return redirect(enter_voucher_url)
    except CourseEnrollmentExistsError:
        messages.error(request, _(u"You have been already enrolled to the course before."))
        return redirect(enter_voucher_url)
    except CourseEnrollmentError:
        messages.error(
            request,
            _(
                u"An error occurred while creating the new course enrollment for user "
                u"'{username}' in course."
            ).format(username=request.user.username)
        )
        return redirect(enter_voucher_url)
    return redirect(reverse('info', args=[unicode(course_id)]))


def get_license(access_code):
    """
    Returns a license for the given access code.
    """
    url = settings.LABSTER_ENDPOINTS.get('voucher_license').format(access_code)

    # Send voucher code to API and get license back
    headers = {
        "authorization": 'Token {}'.format(settings.LABSTER_API_AUTH_TOKEN),
        "accept": 'application/json',
    }
    response = None

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        content = response.json()

        if 'error' in content:
            raise VoucherError(content['error'])

        return content['license']
    except RequestException as ex:
        if getattr(response, 'status_code', None) == 404:
            raise ItemNotFoundError
        else:
            log.exception("Labster API is unavailable:\n%r", ex)
            raise LabsterApiError(_("Labster API is unavailable."))
    except (KeyError, ValueError) as ex:
        log.error("Invalid JSON:\n%r", ex)
        raise LabsterApiError(_("Invalid JSON."))
