import falcon
from feather.resource import Collection, Item

def create_app(resources):
    """Create a falcon app and add a route
    for all the resources

    Args:
        resources (list): A list of ``Collection`` objects to create routes for.
            ``Item`` objects can also be in the list,
            or any other object which inherits/implements ``Collection``.

    Example:
        >>> from feather import create_app
        >>> from feather.resource import Collection, Item
        >>> from feather.schema import MongoSchema
        >>> from marshmallow import fields
        >>> class User(MongoSchema):
        ...   email = fields.Email(required=True)
        ...   name = fields.Str(required=True)
        ...
        >>> user = User()
        >>> resources = (Collection('/users', user), Item('/users/{email}', user))
        >>> api = create_app(resources)

    """
    api = falcon.API()
    for resource in resources:
        api.add_route(resource.uri_template, resource)

    return api
