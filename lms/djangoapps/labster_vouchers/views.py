from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import cache_control
from edxmako.shortcuts import render_to_response


@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def enter_voucher(request):
    """
    Display the Enter Voucher form for student.
    """
    context = {'user': request.user}
    return render_to_response('labster/enter_voucher.html', context)
