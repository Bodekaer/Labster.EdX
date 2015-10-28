import json
import newrelic.agent
import re
import urllib2
from lxml import etree

from dateutil import parser
from datetime import timedelta

from util.cache import cache
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.uploadhandler import StopFutureHandlers
from django.core.mail import EmailMessage
from django.http import Http404, HttpResponse
from django.http.multipartparser import parse_header, ChunkIter
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ParseError
from rest_framework.generics import ListCreateAPIView, CreateAPIView
from rest_framework.parsers import DataAndFiles
from rest_framework.parsers import FormParser, MultiPartParser, BaseParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import XMLRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from labster.api.serializers import (
    ErrorInfoSerializer, DeviceInfoSerializer,
    UserAttemptSerializer, FinishLabSerializer)
from labster.authentication import GetTokenAuthentication
from labster.models import (
    UserSave, ErrorInfo, DeviceInfo, LabProxy, UserAttempt, UnityLog,
    UserAnswer, Mission, ProblemProxy)
from labster.parsers.problem_parsers import MultipleChoiceProblemParser
from labster.renderers import LabsterXMLRenderer, LabsterDirectXMLRenderer
from labster.masters import get_problem
from labster.proxies import get_lab_proxy_as_platform_xml
from labster.utils import get_object_or_none
from labster.wiki_utils import get_all_links


def invoke_xblock_handler(*args, **kwargs):
    from courseware.module_render import _invoke_xblock_handler

    """
    Wrapper so it could be mocked
    """
    return _invoke_xblock_handler(*args, **kwargs)


def get_usage_key():
    from opaque_keys.edx.keys import UsageKey
    return UsageKey


def get_modulestore():
    from xmodule.modulestore.django import modulestore
    return modulestore


def get_lab_by_location(location):
    UsageKey = get_usage_key()
    modulestore = get_modulestore()

    locator = UsageKey.from_string(location)
    descriptor = modulestore().get_item(locator)
    lab_id = descriptor.lab_id
    lab = {}

    quiz_blocks = []
    for _quiz_block in descriptor.get_children():
        problems = []
        for _problem in _quiz_block.get_children():
            problem = {
                'id': unicode(_problem.location),
                'content': _problem.data,
                'platform_xml': _problem.platform_xml,
                'tags': _problem.tags,
            }

            problems.append(problem)

        quiz_block = {
            'id': unicode(_quiz_block.location),
            'slug': _quiz_block.display_name,
            'problems': problems,
        }

        quiz_blocks.append(quiz_block)

    lab.update({
        'lab': {
            'id': int(lab_id),
            'quiz_blocks': quiz_blocks,
        }
    })

    return lab


def parse_platform_xml(xml_string):
    quiz_tree = etree.fromstring(xml_string)
    quiz_element = {
        'name': quiz_tree.tag,
        'attrib': quiz_tree.attrib,
        'children': [],
    }

    for options_tree in quiz_tree.getchildren():
        options_element = {
            'name': options_tree.tag,
            'attrib': options_tree.attrib,
            'children': [],
        }

        for option_tree in options_tree.getchildren():
            options_element['children'].append(
                {
                    'name': option_tree.tag,
                    'attrib': option_tree.attrib,
                    'children': [],
                }
            )

        quiz_element['children'].append(options_element)

    return quiz_element


def parse_edx_xml(xml_string, problem_id):
    parsed_problem = MultipleChoiceProblemParser(xml_string)

    options = parsed_problem.options
    options_element = {
        'name': "Options",
        'attrib': {},
        'children': [],
    }

    for each in options:
        attrib = {'Sentence': each['text']}
        if each['is_correct']:
            attrib['IsCorrectAnswer'] = "true"
        option = {
            'name': "Option",
            'attrib': attrib,
            'children': [],
        }
        options_element['children'].append(option)

    quiz_element = {
        'name': "Quiz",
        'attrib': {
            'Id': problem_id,
            'Sentence': str(parsed_problem.problem).encode('string_escape'),
            'CorrectMessage': str(parsed_problem.solution).encode('string_escape'),
            'WrongMessage': "No. This is incorrect - please try again!",
        },
        'children': [options_element],
    }

    return quiz_element


def get_lab_by_location_for_xml(location):
    lab_by_location = get_lab_by_location(location)

    response_data = {
        'name': "QuizBlocks",
        'attrib': {},
        'children': [],
    }

    for quiz_block in lab_by_location['lab']['quiz_blocks']:
        qb_element = {
            'name': "QuizBlock",
            'attrib': {
                'Id': quiz_block['slug'],
            },
            'children': [],
            'children_tree': [],
        }

        for problem in quiz_block['problems']:
            if problem['platform_xml']:
                quiz_element = parse_platform_xml(problem['platform_xml'])
            else:
                quiz_element = parse_edx_xml(problem['content'], problem['id'])

            qb_element['children'].append(quiz_element)

        response_data['children'].append(qb_element)

    return response_data


class RendererMixin:
    renderer_classes = (XMLRenderer, JSONRenderer)
    charset = 'utf-8'


class LabsterRendererMixin(object):
    renderer_classes = (LabsterXMLRenderer,)
    charset = 'utf-8'

    def get_labster_renderer_context(self):
        return {}

    def get_renderer_context(self):
        ctx = super(LabsterRendererMixin, self).get_renderer_context()
        ctx.update(self.get_labster_renderer_context())
        return ctx


class ParserMixin:
    parser_classes = (FormParser, MultiPartParser,)


class AuthMixin:
    authentication_classes = (TokenAuthentication, SessionAuthentication, GetTokenAuthentication)
    permission_classes = (IsAuthenticated,)


class APIRoot(RendererMixin, AuthMixin, APIView):

    def get(self, request, *args, **kwargs):
        format = kwargs.get('format')
        lab_proxy_detail_url = reverse(
            'labster-api:questions',
            request=request,
            kwargs={'lab_id': 'LAB-ID'},
            format=format)

        answer_problem_url = reverse(
            'labster-api:answer',
            request=request,
            kwargs={'lab_id': 'LAB-ID'},
            format=format)

        save_url = reverse(
            'labster-api:save',
            request=request,
            kwargs={'lab_id': 'LAB-ID'},
            format=format)

        error_url = reverse(
            'labster-api:log-error',
            request=request,
            kwargs={'lab_id': 'LAB-ID'},
            format=format)

        device_url = reverse(
            'labster-api:log-device',
            request=request,
            kwargs={'lab_id': 'LAB-ID'},
            format=format)

        return Response({
            'questions': lab_proxy_detail_url,
            'answer': answer_problem_url,
            'save': save_url,
            'error': error_url,
            'device': device_url,
        })


class UserAuth(RendererMixin, APIView):

    def post(self, request, *args, **kwargs):
        email = request.DATA.get('email')
        password = request.DATA.get('password')
        response_data = {}
        http_status = status.HTTP_200_OK

        if not email or not password:
            response_data['status'] = False

        else:
            try:
                user = User.objects.get(email=email)
            except:
                response_data['status'] = False
            else:
                response_data['status'] = user.check_password(password)

        if response_data['status']:
            token, _ = Token.objects.get_or_create(user=user)
            response_data.update({
                'user_id': user.id,
                'token': token.key,
            })

        else:
            http_status = status.HTTP_400_BAD_REQUEST

        return Response(response_data, status=http_status)


class SendGraphData(AuthMixin, APIView):
    parser_classes = (MultiPartParser, FormParser,)

    def post(self, request, *args, **kwargs):
        user = request.user
        file = request.FILES['file']

        context = {
            'user': user,
        }
        email_html = render_to_string('emails/graph_data.html', context)
        subject = "Graph Data"

        email = EmailMessage(subject, email_html, "no-reply@labster.com", [user.email,])
        email.content_subtype = "html"
        email.attach(file.name, file.read(), file.content_type)
        email.send(fail_silently=False)

        http_status = status.HTTP_200_OK

        return Response(http_status)

    def get(self, request, *args, **kwargs):
        file_url = self.request.QUERY_PARAMS.get('url')

        if not file_url:
            http_status = status.HTTP_204_NO_CONTENT
            return Response(status=http_status)

        response = urllib2.urlopen(file_url)
        user = request.user

        context = {
            'user': user,
        }
        email_html = render_to_string('emails/graph_data.html', context)
        subject = "Graph Data"

        email = EmailMessage(subject, email_html, "no-reply@labster.com", [user.email,])
        email.content_subtype = "html"
        email.attach(file_url.split('/')[-1], response.read(), 'application/octet-stream')
        email.send(fail_silently=False)

        http_status = status.HTTP_200_OK

        return Response(status=http_status)


class CreateSave(AuthMixin, APIView):
    parser_classes = (MultiPartParser,)
    renderer_classes = (JSONRenderer,)
    charset = 'utf-8'

    def get_root_attributes(self):
        file_url = ""
        # if self.user_save:
        #     file_url = self.user_save.save_file.url
        return {
            'FileUrl': file_url,
        }

    def get_labster_renderer_context(self):
        return {
            'root_name': "Save",
            'root_attributes': self.get_root_attributes(),
        }

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        # hack to be able to have multipart form data
        # the content type header needs to be empty and somehow unity sends
        # application/json by default
        # the correct content-type should be: multipart/form-data; boundary=xxx
        try:
            content_type = re.search(r'--(--)?(\w+[^\-\s]+)', request.body).group(2)
        except AttributeError:
            pass
        else:
            request.META['CONTENT_TYPE'] = 'multipart/form-data; boundary={}'.format(content_type)
        return super(CreateSave, self).dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        # http://www.django-rest-framework.org/api-guide/requests#user
        user = request.user
        lab_id = kwargs.get('lab_id')
        http_status = status.HTTP_200_OK

        try:
            lab_proxy = LabProxy.objects.get(id=lab_id)
            self.user_save = UserSave.objects.filter(lab_proxy_id=lab_proxy.id, user_id=user.id).latest('id')
        except (LabProxy.DoesNotExist, UserSave.DoesNotExist):
            http_status = status.HTTP_404_NOT_FOUND

        response_data = {}
        return Response(response_data, status=http_status)

    def pre_save(self, obj):
        obj.user = self.request.user
        lab_id = self.kwargs.get('lab_id')
        obj.lab_proxy = get_object_or_404(LabProxy, id=lab_id)

    def post(self, request, *args, **kwargs):
        http_status = status.HTTP_200_OK
        if not request.user.is_authenticated():
            return Response({}, status=http_status)

        request._load_method_and_content_type()
        request._data, request._files = request._parse()
        user = request.user
        lab_id = kwargs.get('lab_id')

        lab_proxy = get_object_or_404(LabProxy, id=lab_id)
        mission_id = request.POST.get('missionId')
        mission = None
        if mission_id:
            mission = get_object_or_none(Mission, element_id=mission_id, lab=lab_proxy.lab)

        user_attempt = UserAttempt.objects.latest_for_user(lab_proxy, user)
        self.user_save = UserSave.objects.create(
            user=user, lab_proxy=lab_proxy, mission=mission,
            attempt=user_attempt)

        file_name = self.user_save.get_new_save_file_name()
        self.user_save.save_file.save(
            file_name,
            SimpleUploadedFile(file_name, request.FILES.get('data').read()),
            save=True)

        file_url = ''
        if self.user_save.save_file:
            file_url = self.user_save.save_file.url
        response_data = {
            'path': file_url,
        }
        return Response(response_data, status=http_status)


class PlayLab(RendererMixin, ParserMixin, AuthMixin, ListCreateAPIView):

    def get(self, request, *args, **kwargs):
        # http://www.django-rest-framework.org/api-guide/requests#user
        user = request.user
        lab_id = kwargs.get('lab_id')

        lab_proxy = get_object_or_404(LabProxy, id=lab_id)
        user_attempt = UserAttempt.objects.latest_for_user(lab_proxy, user)
        if not user_attempt:
            raise Http404

        serializer = UserAttemptSerializer(user_attempt)
        return Response(serializer.data)

    def pre_save(self, obj, data=None):
        obj.user = self.request.user
        obj.lab_proxy = get_object_or_404(LabProxy, id=self.kwargs.get('lab_id'))

        if obj.is_finished and data.get('play') == '1':
            obj.play_count += 1
            obj.is_finished = False

    def post(self, request, *args, **kwargs):
        data = request.DATA.copy()

        user = request.user
        lab_id = kwargs.get('lab_id')
        lab_proxy = get_object_or_404(LabProxy, id=lab_id)

        user = get_object_or_404(User, id=user.id)
        data.update({
            'user': user,
            'lab_proxy': lab_proxy,
        })

        serializer = UserAttemptSerializer(data=data)
        if serializer.is_valid():
            self.pre_save(serializer.object, data=data)
            serializer.save()
            http_status = status.HTTP_201_CREATED
            return Response(serializer.data, status=http_status)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FinishLab(RendererMixin, ParserMixin, AuthMixin, ListCreateAPIView):

    def get(self, request, *args, **kwargs):
        # http://www.django-rest-framework.org/api-guide/requests#user
        user = request.user

        lab_id = kwargs.get('lab_id')
        lab_proxy = get_object_or_404(LabProxy, id=lab_id)

        user_attempt = UserAttempt.objects.latest_for_user(lab_proxy, user)
        if not user_attempt:
            raise Http404

        serializer = FinishLabSerializer(user_attempt)
        return Response(serializer.data)

    def pre_save(self, obj, data=None):
        obj.user = self.request.user
        lab_id = self.kwargs.get('lab_id')
        obj.lab_proxy = get_object_or_404(LabProxy, id=lab_id)

    def post(self, request, *args, **kwargs):
        data = request.DATA

        user = request.user
        lab_id = kwargs.get('lab_id')
        lab_proxy = get_object_or_404(LabProxy, id=lab_id)

        user = get_object_or_404(User, id=user.id)
        user_attempt = UserAttempt.objects.latest_for_user(lab_proxy, user)
        if not user_attempt:
            raise Http404

        serializer = FinishLabSerializer(instance=user_attempt, data=data)
        if serializer.is_valid():
            self.pre_save(serializer.object, data=data)
            serializer.save()
            http_status = status.HTTP_204_NO_CONTENT
            return Response(serializer.data, status=http_status)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LabSettings(LabsterRendererMixin, AuthMixin, APIView):

    def get_root_attributes(self):
        return {
            'EngineXML': "",
            'NavigationNode': "Classic",
            'CameraMode': "Standard",
            'InputMode': "Mouse",
            'DebugOculus': "true",
            'OuputDebugLog': "true",
        }

    def get_labster_renderer_context(self):
        return {
            'root_name': "Settings",
            'root_attributes': self.get_root_attributes(),
        }

    def get(self, request, *args, **kwargs):
        response_data = {}
        return Response(response_data, status=status.HTTP_200_OK)


class CreateError(LabsterRendererMixin, ParserMixin, AuthMixin, CreateAPIView):
    model = ErrorInfo
    serializer_class = ErrorInfoSerializer

    def get_labster_renderer_context(self):
        return {
            'root_name': "Error",
            'root_attributes': {},
        }

    def pre_save(self, obj):
        obj.user = self.request.user
        lab_id = self.kwargs.get('lab_id')
        obj.lab_proxy = get_object_or_404(LabProxy, id=lab_id)


class CreateDevice(LabsterRendererMixin, ParserMixin, AuthMixin, CreateAPIView):
    model = DeviceInfo
    serializer_class = DeviceInfoSerializer

    def get_labster_renderer_context(self):
        return {
            'root_name': "Device",
            'root_attributes': {},
        }

    def pre_save(self, obj):
        obj.user = self.request.user
        lab_id = self.kwargs.get('lab_id')
        obj.lab_proxy = get_object_or_404(LabProxy, id=lab_id)


class LabProxyView(AuthMixin, APIView):
    renderer_classes = (LabsterDirectXMLRenderer,)
    charset = 'utf-8'

    def get_response_data(self, lab_id):
        lab_proxy = get_object_or_404(LabProxy, id=lab_id)
        lab_proxy_xml = get_lab_proxy_as_platform_xml(lab_proxy)
        response_data = etree.tostring(lab_proxy_xml)
        return response_data

    def get(self, request, format=None, *args, **kwargs):
        lab_id = kwargs.get('lab_id')
        response_data = self.get_response_data(lab_id)
        return Response(response_data)

    def post(self, request, format=None, *args, **kwargs):
        lab_id = kwargs.get('lab_id')
        response_data = self.get_response_data(lab_id)
        return Response(response_data)


class WikiMixin(object):
    def get_root_attributes(self):
        attr = {}
        try:
            attr = {
                'id': self.article_id,
                'title': self.title,
                'slug': self.slug,
            }
        except AttributeError:
            pass

        return attr

    def get_labster_renderer_context(self):
        return {
            'root_name': "Wiki",
            'root_attributes': self.get_root_attributes(),
        }

    def get_wiki_links(self):
        links = get_all_links(self.article)
        wiki_links = [
            {
                'name': "Link",
                'attrib': {
                    'url': link[0],
                    'title': link[1],
                },
                'children': [],
            } for link in links
        ]

        return wiki_links


    def get_response_data(self):
        # ref:
        # https://github.com/Bodekaer/Labster.EdX.django-wiki/blob/66f357e4f6db1b96006ed8e75cd867f7541bb812/wiki/models/article.py#L178
        content_markdown = self.article.current_revision.content

        return {
            'name': "Content",
            'attrib': {},
            'children': [
                {
                    'name': "HTML",
                    'attrib': {},
                    'children': [],
                    'text': self.article.render(),
                },
                {
                    'name': "Markdown",
                    'attrib': {},
                    'children': [],
                    'text': content_markdown,
                },
                {
                    'name': "Links",
                    'attrib': {},
                    'children': self.get_wiki_links(),
                }
            ]
        }


class Wiki(WikiMixin, LabsterRendererMixin, AuthMixin, APIView):

    def _request(self, request, course_id, *args, **kwargs):
        from course_wiki.utils import course_wiki_slug
        from courseware.courses import get_course_by_id
        from opaque_keys.edx.locations import SlashSeparatedCourseKey
        from wiki.models import URLPath, Article

        try:
            # ref:
            # https://github.com/Bodekaer/Labster.EdX/blob/cfcbdc01453150f1025e59c9b6a9a03ace390f4a/lms/djangoapps/course_wiki/views.py#L39
            course = get_course_by_id(SlashSeparatedCourseKey.from_deprecated_string(course_id))
        except ValueError:
            raise Http404

        course_slug = course_wiki_slug(course)

        url_path = URLPath.get_by_path(course_slug, select_related=True)

        try:
            article = Article.objects.get(id=url_path.article.id)
        except Article.DoesNotExist:
            article = None

        self.article_id = str(url_path.article.id)
        self.slug = course_slug
        self.title = unicode(article)
        self.article = article

        response_data = self.get_response_data()
        return Response(response_data)

    def post(self, request, course_id, *args, **kwargs):
        return self._request(request, course_id, *args, **kwargs)

    def get(self, request, course_id, *args, **kwargs):
        return self._request(request, course_id, *args, **kwargs)


class ArticleSlugCache(object):
    """
    A cache for article slugs.
    """
    def _cache_key(self, slug):
        """Creates a cache key."""
        return u"labster.api.views.ArticleSlug.{}".format(unicode(slug))

    def get(self, key):
        """
        Retun data from django's cache.
        """
        return cache.get(self._cache_key(key))

    def set(self, key, data):
        """
        Update the cache.
        """
        cache.set(self._cache_key(key), data, 60 * 60 * 4)  # 4 hours


class ArticleSlug(WikiMixin, LabsterRendererMixin, AuthMixin, APIView):
    # Valid locales in our wiki
    valid_locales = ['da']

    def _request(self, request, article_slug, *args, **kwargs):
        from wiki.core.exceptions import NoRootURL
        from wiki.models import URLPath, Article

        initial_article_slug = article_slug
        article_slug_cache = ArticleSlugCache()
        cached_data = article_slug_cache.get(initial_article_slug)
        # if the data is already cached, just return it.
        if cached_data:
            return Response(cached_data)

        # since we already have article slug we don't need to search the course
        # article slug is unique
        try:
            url_path = URLPath.get_by_path(article_slug, select_related=True)
        except (NoRootURL, ObjectDoesNotExist):
            # Get english article if exists
            split_slug = article_slug.split('-')
            locale = split_slug[-1]
            if len(split_slug) > 1 and (locale in ArticleSlug.valid_locales):
                article_slug = '-'.join(split_slug[:-1])
                try:
                    url_path = URLPath.get_by_path(
                        article_slug, select_related=True)
                except (NoRootURL, ObjectDoesNotExist):
                    return Response({}, status=status.HTTP_404_NOT_FOUND)
            else:
                return Response({}, status=status.HTTP_404_NOT_FOUND)

        try:
            article = Article.objects.get(id=url_path.article.id)
        except Article.DoesNotExist:
            article = None

        self.article_id = str(url_path.article.id)
        self.slug = article_slug
        self.title = unicode(article)
        self.article = article

        response_data = self.get_response_data()
        article_slug_cache.set(initial_article_slug, response_data)
        return Response(response_data)

    def post(self, request, article_slug, *args, **kwargs):
        return self._request(request, article_slug, *args, **kwargs)

    def get(self, request, article_slug, *args, **kwargs):
        return self._request(request, article_slug, *args, **kwargs)


class ArticleLinks(WikiMixin, LabsterRendererMixin, AuthMixin, APIView):

    def _request(self, request, article_slug, *args, **kwargs):
        self.get_article(article_slug)
        response_data = self.get_response_data()
        return Response(response_data)

    def get_article(self, article_slug):
        from wiki.core.exceptions import NoRootURL
        from wiki.models import URLPath, Article

        # since we already have article slug we don't need to search the course
        # article slug is unique
        try:
            url_path = URLPath.get_by_path(article_slug, select_related=True)
        except (NoRootURL, ObjectDoesNotExist):
            return Response({}, status=status.HTTP_404_NOT_FOUND)

        try:
            article = Article.objects.get(id=url_path.article.id)
        except Article.DoesNotExist:
            article = None

        self.article_id = str(url_path.article.id)
        self.slug = article_slug
        self.title = unicode(article)
        self.article = article

        return article

    def links_xml_format(self, links):
        return [
            {
                'name': "Link",
                'attrib': {
                    'url': link[0],
                    'title': link[1],
                },
                'children': [],
            } for link in links
        ]

    def get_response_data(self):
        links = get_all_links(self.article)
        return {
            'name': "Links",
            'attrib': {},
            'children': self.links_xml_format(links),
        }

    def get(self, request, article_slug, *args, **kwargs):
        return self._request(request, article_slug, *args, **kwargs)

    def post(self, request, article_slug, *args, **kwargs):
        return self._request(request, article_slug, *args, **kwargs)


class AnswerProblem(ParserMixin, AuthMixin, APIView):

    renderer_classes = (JSONRenderer,)

    def __init__(self, *args, **kwargs):
        self.usage_key = get_usage_key()
        self.modulestore = get_modulestore()
        super(AnswerProblem, self).__init__(*args, **kwargs)

    def bad_request_response(self, request, lab_proxy, error_message):
        user = request.user
        post_data = request.POST.copy()
        log_type = 'quiz_statistic'
        url = request.build_absolute_uri()
        request_method = request.method

        try:
            # try to log
            # because why not
            UnityLog.new(user, lab_proxy, log_type, post_data, url, request_method)
        except:
            pass

        response_data = {
            'message': error_message,
            'post': post_data,
        }
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, *args, **kwargs):
        response_data = {}
        lab_id = kwargs.get('lab_id')
        lab_proxy = get_object_or_404(LabProxy, id=lab_id)
        user = request.user

        score = request.POST.get('Score')
        question = request.POST.get('QuizQuestion')
        completion_time = request.POST.get('CompletionTime')
        chosen_answer = request.POST.get('ChosenAnswer', '').strip()
        start_time = request.POST.get('StartTime')
        play_count = request.POST.get('PlayCount')
        attempt_count = request.POST.get('AttemptCount')
        quiz_id = request.POST.get('QuizId', '')
        answer_index = request.POST.get('AnswerIndex', 0)
        is_view_theory_clicked = request.POST.get('isViewTheoryClicked', 'False') == 'True'

        if not all([
            score is not None,
            completion_time is not None,
            chosen_answer is not None,
            start_time is not None,
            play_count is not None,
            attempt_count is not None,
        ]):

            return self.bad_request_response(
                request, lab_proxy, "Missing required data")

        start_time = parser.parse(start_time).replace(tzinfo=timezone.utc)
        completion_time = float(completion_time)
        end_time = start_time + timedelta(seconds=completion_time)

        problem = get_problem(lab_proxy, quiz_id, question)
        if not problem:
            return self.bad_request_response(
                request, lab_proxy, "Missing problem")

        correct_answers = problem.correct_answer_texts
        if not quiz_id:
            try:
                problem_proxy = ProblemProxy.objects.get(
                    lab_proxy=lab_proxy, problem=problem)
            except ProblemProxy.DoesNotExist:
                pass
            else:
                quiz_id = problem_proxy.quiz_id

        user_attempt = UserAttempt.objects.latest_for_user(lab_proxy, user)
        if not user_attempt:
            user_attempt = UserAttempt.objects.create(lab_proxy=lab_proxy, user=user)

        try:
            answer_index = int(answer_index)
        except:
            answer_index = 0

        is_correct = chosen_answer in correct_answers
        UserAnswer.objects.create(
            attempt=user_attempt,
            answer_string=chosen_answer,
            attempt_count=attempt_count,
            completion_time=completion_time,
            correct_answer=":::".join(correct_answers),
            end_time=end_time,
            is_correct=is_correct,
            lab_proxy=lab_proxy,
            play_count=play_count,
            problem=problem,
            question=problem.sentence,
            score=score,
            start_time=start_time,
            user=user,
            quiz_id=quiz_id,
            answer_index=answer_index,
            is_view_theory_clicked=is_view_theory_clicked,
        )
        response_data = {'correct': is_correct}
        return Response(response_data, status=status.HTTP_201_CREATED)


class UnityPlayLab(ParserMixin, AuthMixin, APIView):

    renderer_classes = (JSONRenderer,)

    def bad_request_response(self, request, lab_proxy, error_message):
        user = request.user
        post_data = request.POST.copy()
        log_type = 'player_start_end'
        url = request.build_absolute_uri()
        request_method = request.method

        try:
            # try to log
            # because why not
            UnityLog.new(user, lab_proxy, log_type, post_data, url, request_method)
        except:
            pass

        response_data = {
            'message': error_message,
            'post': post_data,
        }
        return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request, *args, **kwargs):
        lab_id = kwargs.get('lab_id')
        lab_proxy = get_object_or_404(LabProxy, id=lab_id)

        start_end_type = request.POST.get('StartEndType')
        try:
            start_end_type = int(start_end_type)
        except TypeError:
            return self.bad_request_response(
                request, lab_proxy, "Bad StartEndType format")
        else:
            if start_end_type not in [1, 2]:
                return self.bad_request_response(
                    request, lab_proxy, "Bad StartEndType format")

        user = request.user
        if start_end_type == 1:

            user_attempts = UserAttempt.objects.filter(
                lab_proxy=lab_proxy, user=user, is_finished=False).order_by('-id')
            if not user_attempts.exists():
                UserAttempt.objects.create(lab_proxy=lab_proxy, user=user, is_finished=False)

        response_data = {'status': 'ok'}
        return Response(response_data, status=status.HTTP_201_CREATED)


class CreateLog(ParserMixin, AuthMixin, APIView):

    renderer_classes = (JSONRenderer,)

    def post(self, request, *args, **kwargs):
        log_type = kwargs.get('log_type')
        lab_id = kwargs.get('lab_id')

        lab_proxy = get_object_or_404(LabProxy, id=lab_id)
        user = request.user
        message = request.POST.copy()
        url = request.build_absolute_uri()
        request_method = request.method

        UnityLog.new(user, lab_proxy,
                     log_type, message, url, request_method)
        response_data = {'status': 'ok'}
        return Response(response_data, status=status.HTTP_201_CREATED)


class CreateUnityLog(ParserMixin, AuthMixin, APIView):

    renderer_classes = (JSONRenderer,)

    def post(self, request, *args, **kwargs):
        nr_transaction = newrelic.agent.current_transaction()

        lab_id = kwargs.get('lab_id')
        with newrelic.agent.FunctionTrace(nr_transaction, "lab_proxy_get_object_or_404"):
            lab_proxy = get_object_or_404(LabProxy, id=lab_id)

        user = request.user
        message = request.POST.get('message', '')

        url = request.build_absolute_uri()

        request_method = request.method
        with newrelic.agent.FunctionTrace(nr_transaction, "UnityLog.new_unity_log"):
            UnityLog.new_unity_log(user, lab_proxy, message, url, request_method)

        response_data = {'status': 'ok'}
        return Response(response_data, status=status.HTTP_201_CREATED)


class LoadMission(ParserMixin, AuthMixin, APIView):

    renderer_classes = (JSONRenderer,)

    def post(self, request, *args, **kwargs):
        lab_id = kwargs.get('lab_id')
        mission_id = request.DATA.get('mission_id')
        lab_proxy = get_object_or_404(LabProxy, id=lab_id)
        user = request.user
        http_status = status.HTTP_200_OK

        # if not mission_id, new game
        if mission_id:
            try:
                user_save = UserSave.objects.get(
                    lab_proxy=lab_proxy,
                    user=user,
                    mission__element_id=mission_id)
            except UserSave.DoesNotExist:
                http_status = status.HTTP_400_BAD_REQUEST
            else:
                user_save.attempt.mark_active()
        else:
            UserAttempt.objects.filter(
                lab_proxy=lab_proxy, user=user, is_finished=False).update(
                    is_finished=True, finished_at=timezone.now())

            # set is_current_active in other attempts to false
            UserAttempt.objects.filter(lab_proxy=lab_proxy, user=user).update(is_current_active=False)
            # create new active user attempt
            UserAttempt.objects.create(lab_proxy=lab_proxy, user=user, is_current_active=True)

        response_data = {}
        return Response(response_data, status=http_status)


def collect_response(request, action):
    return HttpResponse('ok')
