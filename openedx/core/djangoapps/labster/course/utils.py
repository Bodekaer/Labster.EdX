""" Labster Course utils. """
import logging

from django.contrib.auth.models import User
from contentstore.utils import add_instructor, remove_all_instructors
from openedx.core.djangoapps.labster.exceptions import LtiPassportError

log = logging.getLogger(__name__)


def set_staff(course_key, emails):
    """
    Sets course staff.
    """
    remove_all_instructors(course_key)
    for email in emails:
        try:
            user = User.objects.get(email=email)
            add_instructor(course_key, user, user)
        except User.DoesNotExist:
            log.info('User with email %s does not exist', email)


class LtiPassport(object):
    """
    Works with lti passports.
    """
    slots = ['lti_id', 'consumer_key', 'secret_key']

    def __init__(self, passport_str):
        self.lti_id, self.consumer_key, self.secret_key = self.parse(passport_str)

    @classmethod
    def parse(cls, passport_str):
        """
        Parses a `passport_str (str)` and retuns lti_id, consumer key, secret key.
        """
        try:
            return tuple(i.strip() for i in passport_str.split(':'))
        except ValueError:
            msg = _('Could not parse LTI passport: {lti_passport}. Should be "id:key:secret" string.').format(
                    lti_passport='{0!r}'.format(passport_str)
            )
            raise LtiPassportError(msg)

    @staticmethod
    def construct(lti_id, consumer_key, secret_key):
        """
        Contructs lti passport.
        """
        return ':'.join([lti_id, consumer_key, secret_key])

    def as_dict(self):
        return dict((prop, getattr(self, prop, None)) for prop in self.slots)

    def __str__(self):
        return LtiPassport.construct(self.lti_id, self.consumer_key, self.secret_key)

    def __unicode__(self):
        return unicode(str(self))
