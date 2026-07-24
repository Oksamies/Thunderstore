"""Social-auth URL overrides.

social-auth-app-django 6.0 made the login "begin" view POST-only (CSRF
hardening). The legacy Django frontend links to it with GET (`<a href>`), so we
re-expose a GET-capable begin view here to keep those login links working, while
reusing social_django's complete/disconnect views unchanged. Hardening the
legacy login links to POST forms is a possible follow-up.
"""
from django.urls import path
from django.views.decorators.cache import never_cache
from social_core.actions import do_auth
from social_django.utils import psa
from social_django.views import complete, disconnect

app_name = "social"


@never_cache
@psa("social:complete")
def begin(request, backend):
    return do_auth(request.backend)


urlpatterns = [
    path("login/<str:backend>/", begin, name="begin"),
    path("complete/<str:backend>/", complete, name="complete"),
    path("disconnect/<str:backend>/", disconnect, name="disconnect"),
    path(
        "disconnect/<str:backend>/<int:association_id>/",
        disconnect,
        name="disconnect_individual",
    ),
]
