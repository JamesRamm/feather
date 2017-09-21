"""Hooks for working with a ``FeatherResource``
"""
import falcon

def validate_content_type(req, resp, resource, params):
    """Validate the content type of a ``FeatherResource``
    """
    if (resource.allowed_content_types
            and req.content_type
            not in resource.allowed_content_types):
        raise falcon.HTTPUnsupportedMediaType(
            'Content type should be one of {}'.format(resource.allowed_content_types)
        )
