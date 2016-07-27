"""
URLs for the Labster voucher system.
"""
from django.conf.urls import patterns, url


urlpatterns = patterns(
    '',
    url(r'^enter/$',
        'labster_vouchers.views.enter_voucher', name='enter_voucher'),
)

