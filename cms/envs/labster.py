from .aws import *  # pylint: disable=wildcard-import, unused-wildcard-import


LABSTER_SETTINGS = ENV_TOKENS.get('LABSTER_SETTINGS', {})
LABSTER_AUTH = AUTH_TOKENS.get('LABSTER_AUTH', {})

FEATURES['CUSTOM_COURSES_EDX'] = True
LABSTER_FEATURES = {
    "ENABLE_WIKI": True,
}

ENV_LABSTER_FEATURES = LABSTER_SETTINGS.get('LABSTER_FEATURES', LABSTER_FEATURES)
for feature, value in ENV_LABSTER_FEATURES.items():
    FEATURES[feature] = value

INSTALLED_APPS += (
    'rest_framework.authtoken',
    'openedx.core.djangoapps.labster.course',
)

LABSTER_WIKI_LINK = LABSTER_SETTINGS.get('LABSTER_WIKI_LINK', 'https://theory.labster.com/')

# Sentry integration config
RAVEN_CONFIG = AUTH_TOKENS.get('RAVEN_CONFIG', {})
if RAVEN_CONFIG.get('dsn'):
    INSTALLED_APPS += ('raven.contrib.django.raven_compat',)

# https://github.com/edx/edx-platform/wiki/Optional-Password-Policy-Enforcement
PASSWORD_MIN_LENGTH = 8
PASSWORD_COMPLEXITY = {
    'ALPHABETIC': 1,
    'NUMERIC': 1,
}
