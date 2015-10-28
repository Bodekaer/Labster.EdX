import json
from django.views.decorators.cache import cache_control
import newrelic.agent
import requests

from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.mail import EmailMessage
from django.http import Http404, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.http import HttpResponse
from django.contrib import messages
from django.shortcuts import redirect
from django_future.csrf import ensure_csrf_cookie
from django.contrib.auth.models import AnonymousUser
from django.db.models import Count

from edxmako.shortcuts import render_to_response, render_to_string

from util.cache import cache, cache_for_every_user
from courseware.courses import get_courses, sort_by_announcement

from labster.courses import get_popular_courses
from labster.models import UserAttempt, Lab
from labster_frontend.demo_courses import labsterify_courses
from labster_search.search import get_courses_from_keywords


@ensure_csrf_cookie
@cache_control(private=True)
@cache_for_every_user()
def index(request, user=AnonymousUser()):
    '''
    Redirects to main page -- info page if user authenticated, or marketing if not
    '''

    if settings.COURSEWARE_ENABLED and request.user.is_authenticated():
        return redirect(reverse('dashboard'))

    if settings.FEATURES.get('AUTH_USE_CERTIFICATES'):
        from external_auth.views import ssl_login
        # Set next URL to dashboard if it isn't set to avoid
        # caching a redirect to / that causes a redirect loop on logout
        if not request.GET.get('next'):
            req_new = request.GET.copy()
            req_new['next'] = reverse('dashboard')
            request.GET = req_new
        return ssl_login(request)

    # The course selection work is done in courseware.courses.
    domain = settings.FEATURES.get('FORCE_UNIVERSITY_DOMAIN')  # normally False
    # do explicit check, because domain=None is valid
    if domain is False:
        domain = request.META.get('HTTP_HOST')

    cached_data = cache.get('labster.landing.view.index')
    if cached_data:
        return render_to_response('labster_landing.html', cached_data)

    courses = get_courses(user, domain=domain)
    courses = sort_by_announcement(courses)
    # get 5 popular labs
    user_attempts = UserAttempt.objects.all().values('lab_proxy__lab').annotate(total=Count('lab_proxy__lab')).order_by('-total')
    labs_id = []

    # get the lab foreign key
    for lab_id in user_attempts:
        labs_id.append(lab_id['lab_proxy__lab'])

    # get course_id
    courses_id = Lab.objects.filter(id__in=labs_id).values_list('demo_course_id', flat=True)
    list_courses_id = []
    for course_id in courses_id:
        if not course_id:
            continue
        list_courses_id.append(course_id)

    # get courses based on course id
    popular_labs = get_popular_courses(list_courses_id)[:6]
    courses = labsterify_courses(courses)
    popular_labs = labsterify_courses(popular_labs)

    course_list_view = render_to_string('labster_course_listing.html', {'courses': courses})
    popular_labs_view = render_to_string('labster_course_listing.html', {'courses': popular_labs})
    data_to_cache = {
        'course_list_view': course_list_view,
        'popular_labs_view': popular_labs_view,
    }
    cache.set('labster.landing.view.index', data_to_cache, 60 * 60 * 4)
    return render_to_response('labster_landing.html', data_to_cache)


@ensure_csrf_cookie
@cache_control(private=True)
@cache_for_every_user()
def courses(request, user=AnonymousUser()):
    """
    Render the "find courses" page. If the marketing site is enabled, redirect
    to that. Otherwise, if subdomain branding is on, this is the university
    profile page. Otherwise, it's the edX courseware.views.courses page
    """

    if not settings.FEATURES.get('COURSES_ARE_BROWSABLE'):
        raise Http404

    # The course selection work is done in courseware.courses.
    domain = settings.FEATURES.get('FORCE_UNIVERSITY_DOMAIN')  # normally False
    # do explicit check, because domain=None is valid
    if domain is False:
        domain = request.META.get('HTTP_HOST')

    referer = request.META.get('HTTP_REFERER', request.build_absolute_uri())

    keywords = request.GET.get('q', '').strip()
    need_to_cache = False
    if keywords:
        courses = get_courses_from_keywords(keywords)
    else:
        cached_data = cache.get('labster.landing.view.courses')
        if cached_data:
            return render_to_response('courseware/labster_courses.html', cached_data)

        courses = get_courses(user, domain=domain)
        courses = sort_by_announcement(courses)
        need_to_cache = True

    courses = labsterify_courses(courses)
    course_list_view = render_to_string('labster_course_listing.html', {'courses': courses})
    context = {
        'keywords': keywords,
        'referer': referer,
        'course_list_view': course_list_view,
        'len_courses': len(courses),
    }
    if need_to_cache:
        cache.set('labster.landing.view.courses', context, 60 * 60 * 4)

    return render_to_response('courseware/labster_courses.html', context)


def contact_form(request):
    if request.method == 'POST':
        subject = "Contact Form"
        name = request.POST.get('name')
        email = request.POST.get('email')
        message = request.POST.get('message')
        message = message.encode('utf-8')
        body = "<p>Name: {0}</p><p>Email: {1}</p><p>Message: </p><p>{2}</p>".format(name, email, message)

        email = EmailMessage(subject, body, email, ['please-reply@labster.com'])
        email.content_subtype = "html"
        email.send(fail_silently=False)

        messages.success(request, 'Thank you for contacting us. We will get back to you as soon as possible.', extra_tags='safe')

        return HttpResponseRedirect('/contact#feedbackForm')

    else:
        messages.success(request, 'Some error occurred in sending mail.', extra_tags='safe')

        return HttpResponseRedirect('/contact#feedbackForm')


def fetch_career_data(request):
    headers = {}
    url = 'http://web.labster.com/rbcount.php'
    resp = requests.get(url, headers=headers)

    return HttpResponse(resp.content)


def redirect_to_old(request, path=''):
    old_site = "http://web.labster.com/{}".format(path)
    return HttpResponsePermanentRedirect(old_site)
