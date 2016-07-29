import requests
import logging

from requests.exceptions import RequestException
from django.contrib import messages
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.shortcuts import redirect
from django.conf import settings

from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_http_methods
from edxmako.shortcuts import render_to_response
from enrollment.api import add_enrollment
from labster_course_license.models import CourseLicense
from labster_vouchers import forms


log = logging.getLogger(__name__)


@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def enter_voucher(request):
    """
    Display the Enter Voucher form for student.
    """
    context = {'user': request.user}
    return render_to_response('labster/enter_voucher.html', context)


@require_http_methods(["POST"])
def activate_voucher(request):
    """
    Gets license code from API, fetches related course_id and enrolls student.
    """
    form = forms.ValidationForm(request.POST)
    enter_voucher_url = reverse('enter_voucher')
    if form.is_valid():
        data = form.cleaned_data
        code = data['code']
        headers = {
            "authorization": 'Token {}'.format(settings.LABSTER_API_AUTH_TOKEN),
            "accept": 'application/json',
        }
        url = settings.LABSTER_ENDPOINTS.get('voucher_license').format(code=code)

        # Send voucher code to API and get license back
        try:
            api_response = requests.get(url, headers=headers)
            if api_response.status_code != 200:
                response_data = {}
            else:
                response_data = api_response.json()
        except RequestException as ex:
            log.exception("An error occured during Labster API request:\n%r", ex)
            messages.error(request, _("An error occured during Labster API request: {}").format(ex))
            return redirect(enter_voucher_url)

        # Search for voucher license
        try:
            lic = CourseLicense.objects.get(license_code=response_data.get('license'))
        except CourseLicense.DoesNotExist:
            log.exception("Voucher related license is not found. Code: {}".format(code))
            messages.error(
                request,
                _("Voucher code `{}` is not valid. Please contact Labster support team.").format(code)
            )
            return redirect(enter_voucher_url)

        course_id = unicode(lic.course_id)
        # enroll student to course
        add_enrollment(request.user, course_id)
        # redirect student to course
        return redirect(reverse('info', args=[course_id]))

