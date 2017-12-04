"""
Management command to obfuscate users data by email or in course.
"""
import string
import random
from itertools import chain
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from student.models import CourseEnrollment, CourseEnrollmentAllowed

from labster_course_license.models import CourseLicense


def action_decorator(action, field_name):
    """
    Decorator applies action to the provided value if value is not empty.
    Prints logs for better process transparency.
    """
    def wrapper(val):
        if val:
            new_val = action(val)
            print("Calling action `%s` for the attr `%s` with value `%s`. Resulting value `%s`" % (
                action, field_name, val, new_val
            ))
            return new_val
        else:
            print("`%s` attr has empty value. Skip obfuscation" % field_name)
    return wrapper


class Command(BaseCommand):
    """
    Obfuscate user credentials by course license or by email.
    """
    help = '''
    Obfuscate user credentials for course license or by email.
    '''

    def add_arguments(self, parser):
        """
        Add arguments to the command parser.
        """
        parser.add_argument(
            '--licenses',
            dest='licenses',
            nargs='+',
            help='List of course licenses whose users should be obfuscated',
        )
        parser.add_argument(
            '--emails',
            dest='emails',
            nargs='+',
            help='List of user emails which should be obfuscated',
        )

    def handle(self, *args, **options):
        """
        Execute the command.
        """
        licenses = options['licenses']
        emails = options['emails']

        user_emails = set()

        if licenses:
            for lic in licenses:
                print ("Processing license %s" % lic)
                try:
                    ccx = CourseLicense.objects.get(license_code=lic).course_id

                    enrolled_users = CourseEnrollment.objects.filter(course_id=ccx).values_list(
                        'user__email', flat=True
                    ).exclude(user__email__contains='labster.com')
                    not_enrolled_users = CourseEnrollmentAllowed.may_enroll_and_unenrolled(ccx).values_list(
                        'email', flat=True
                    )

                    all_users = chain(not_enrolled_users, enrolled_users)

                    user_emails |= set(all_users)
                except CourseLicense.DoesNotExist:
                    pass

        if emails:
            user_emails |= set(emails)

        self.obfuscate_users(user_emails)

    def obfuscate_users(self, user_emails):
        """
        Obfuscates user model fields: names, email.
        """
        users = User.objects.filter(email__in=user_emails)

        field_actions = {
            'first_name': self.generate_random_string,
            'last_name': self.generate_random_string,
            'username': self.generate_random_string,
            'profile.name': self.generate_random_string,
            'profile.mailing_address': self.generate_random_string,
            'email': self.obfuscate_email
        }

        self.obfuscate_names_emails(users, field_actions)

    @staticmethod
    def obfuscate_names_emails(query_set, field_actions):
        """
        Obfuscates objects name, email and other fields.
        """
        fields_select = set([key.split('.')[0] if '.' in key else key for key in field_actions.keys()])
        for obj in query_set.only(*fields_select):
            print("Obfuscating data for %s" % obj)
            values = {}
            references = {}
            for field, action in field_actions.items():
                action = action_decorator(action, field)
                if '.' in field:
                    # one2one relation or foreign key found
                    names = field.split('.')
                    # get relation field value
                    val = getattr(getattr(obj, names[0]), names[1], '')
                    if not (names[0] in references):
                        references[names[0]] = {}
                    references[names[0]].update({names[1]: action(val)})
                else:
                    val = getattr(obj, field, '')
                    values[field] = action(val)

            if values:
                obj.__class__.objects.filter(id=obj.id).update(**values)

            if references:
                for rel, item in references.items():
                    _class = getattr(obj, rel).__class__
                    _id = getattr(obj, rel).id
                    _class.objects.filter(id=_id).update(**item)

    @staticmethod
    def generate_random_string(text):
        """
        Create a string of random characters of specified length.
        """
        chars = [char for char in string.ascii_lowercase]
        return string.join((random.choice(chars) for __ in range(len(text))), '')

    def obfuscate_email(self, email):
        """
        Return random string of the same length as input value.
        """
        obfuscated = self.generate_random_string(email)
        return ''.join([obfuscated[idx] if ch not in ['@', '.'] else ch for idx, ch in enumerate(email)])
