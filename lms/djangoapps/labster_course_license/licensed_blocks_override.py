"""
API related to providing field overrides for individual students.  This is used
by the individual custom courses feature.
"""
import logging
from courseware.field_overrides import FieldOverrideProvider
from labster_course_license.models import LicensedCoursewareItems, CourseLicense
from labster_course_license.utils import get_block_course_key
from ccx_keys.locator import CCXLocator
from ccx.overrides import get_current_ccx


log = logging.getLogger(__name__)


class LicensedBlocksOverrideProvider(FieldOverrideProvider):
    """
    A concrete implementation of
    :class:`~courseware.field_overrides.FieldOverrideProvider` which allows for
    overrides to be made on a per user basis.
    """
    def get(self, block, name, default):
        """
        Just call the get_override_for_ccx method if there is a ccx
        """
        if name != 'visible_to_staff_only':
            return default
        course_key = get_block_course_key(block)
        if course_key is not None:
            # find the ccx that is active for block course
            try:
                ccx = get_current_ccx(course_key)
                if ccx:
                    course_key = CCXLocator.from_course_locator(course_key, ccx.id)
                    return is_visible_to_staff_only(course_key, block, default)
            except ValueError:
                # not a CourseKey instance
                pass
        return default

    @classmethod
    def enabled_for(cls, course):
        """
        CCX field overrides are enabled per-course

        protect against missing attributes
        """
        return getattr(course, 'enable_ccx', False)


def is_visible_to_staff_only(course_key, block, default):
    """
    Show block if its licensed simulations intersect with course simulations.
    """
    # we need to filter LicensedCoursewareItems properly by block location
    # just `block.location` will result in all courseware items are shown
    try:
        location = block.location.to_block_locator()
    except AttributeError:
        location = block.location

    # teacher or course staff can hide blocks in studio manually
    # we need to return `default` instead of `False`
    # this will allow to stay in sync with studio visibility edits
    try:
        # List of actual simulations in the block (chapter, seq, vertical).
        item = LicensedCoursewareItems.objects.get(block=location)
        # List of licensed simulations in the course
        course_license = CourseLicense.objects.get(course_id=course_key)
    except LicensedCoursewareItems.DoesNotExist, CourseLicense.DoesNotExist:
        # we have regular block without simulations inside (text, video or other type)
        return default

    available_simulations = set(course_license.simulations)
    actual_simulations = set(item.simulations)

    if len(actual_simulations.intersection(available_simulations)):
        # there are licensed simulations so block should be shown by default
        return default
    else:
        return True
