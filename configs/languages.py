from flask_babel import gettext as _
import collections

supported_languages = {
    "en" : _("English"),
    "es" : _("Spanish"),
    "pt" : _("Portuguese")
}

supported_languages = collections.OrderedDict(supported_languages)