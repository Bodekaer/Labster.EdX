"""
Labster admin page for student enrollments.
"""
from django.contrib.admin.sites import NotRegistered
from django.utils.translation import ugettext_lazy as _
from ratelimitbackend import admin
from student.admin import CourseEnrollmentAdmin
from student.models import (
    CourseAccessRole,
    CourseEnrollment,
    CourseEnrollmentAllowed,
)


class LabsterRolesFilter(admin.SimpleListFilter):
    """
    Returns the filtered queryset based on the roles value.
    """
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _('Roles')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'roles'
    list_roles = (
        ('student', _('Student')),
    )

    def lookups(self, request, model_admin):  # pylint: disable=unused-argument
        """
        Returns a list of tuples in this case is list of roles. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return self.list_roles

    def queryset(self, request, queryset):  # pylint: disable=unused-argument
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        exclude_list_roles = (
            'beta_testers',
            'ccx_coach',
            'course_creator_group',
            'library_user',
            'finance_admin',
            'instructor',
            'sales_admin',
            'staff',
            'support'
        )

        if self.value():
            return queryset.exclude(user__courseaccessrole__role__in=exclude_list_roles)


class LabsterCourseEnrollmentAllowedAdmin(admin.ModelAdmin):
    """
    Admin interface for the CourseEnrollmentAllowed model.
    """
    list_display = ('email', 'course_id', 'auto_enroll', 'created')
    search_fields = ('email', 'course_id')


class LabsterCourseEnrollmentAdmin(CourseEnrollmentAdmin):
    """
    Admin interface for the CourseEnrollment model.
    """
    list_display = ('id', 'course_id', 'mode', 'user', 'email', 'roles', 'is_active')
    list_filter = (LabsterRolesFilter, 'mode', 'is_active',)
    search_fields = ('course_id', 'mode', 'user__username', 'user__email')

    def email(self, obj):
        return obj.user.email

    def roles(self, obj):
        roles = CourseAccessRole.objects.filter(user=obj.user, course_id=obj.course_id).values_list('role', flat=True)
        user_roles = ', '.join(role for role in roles)
        return user_roles if user_roles != '' else 'student'


# To apply new admin models we must first un-register the CourseEnrollmentAllowed and CourseEnrollment model
# since it may also be registered by the auth app.
try:
    admin.site.unregister(CourseEnrollmentAllowed)
    admin.site.unregister(CourseEnrollment)
except NotRegistered:
    pass

# Reapply new admin for CourseEnrollmentAllowed and CourseEnrollment models.
admin.site.register(CourseEnrollmentAllowed, LabsterCourseEnrollmentAllowedAdmin)
admin.site.register(CourseEnrollment, LabsterCourseEnrollmentAdmin)
