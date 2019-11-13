from werkzeug.routing import Map, Rule, Submount
from werkzeug.routing import UnicodeConverter, BaseConverter, AnyConverter

import settings


class ListConverter(UnicodeConverter):
    def to_python(self, value):
        value = super(ListConverter, self).to_python(value)
        return value.split("+")

    def to_url(self, value):
        if value:
            if not isinstance(value, str):
                encoded = [super(ListConverter, self).to_url(x) for x in value]
                value = "+".join(encoded)
        return value


class AppConverter(AnyConverter):
    def __init__(self, map):
        super().__init__(map, *settings.PAGES)


class EntityConverter(BaseConverter):
    regex = r"(?:ccg_id|practice_id|lab|test_code|result_category)"


url_map = Map(
    [
        Submount(
            "/data",
            [
                Rule("/<app:page_id>", endpoint="index"),
                Rule(
                    "/<app:page_id>/by/<entity_type:groupby>/showing/<entity_type:practice_filter_entity>/<list:entity_ids_for_practice_filter>/numerators/<list:numerators>/denominators/<list:denominators>/filter/<string:result_filter>",
                    endpoint="analysis",
                ),
            ],
        )
    ],
    converters={
        "list": ListConverter,
        "app": AppConverter,
        "entity_type": EntityConverter,
    },
)

urls = url_map.bind(
    "hostname"
)  # Required by werkzeug for redirects, although we never use
