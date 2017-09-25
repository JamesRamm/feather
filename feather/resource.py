"""Resource classes for creating a JSON restful API.
"""
import mimetypes
import falcon
import simplejson
from feather.hooks import validate_content_type
from feather import errors


def basic_error_handler(error_dict):
    """Handle an error dictionary returned by
    a marshmallow schema
    """
    # Duplicate keys indicate a conflict since the object already exists
    print(error_dict)
    if errors.DUPLICATE_KEY in error_dict:
        raise falcon.HTTPConflict('Duplicate Key', error_dict[errors.DUPLICATE_KEY])
    elif error_dict:
        raise falcon.HTTPBadRequest('Validation Error', error_dict)


class FeatherResource(object):
    """Base class used for setting a uri_template, allowed content types
    and HTTP methods provided.

    By encapsulating the URI, we can provide factory methods
    for routing, allowing us to specify the resource and its' uri
    in one place

    Methods are dynamically assigned in order to allow a single Resource class
    to be created for different resources/with different requirements.
    (E.g. create a read-only collection by only passing ``('get',)`` when
    instantiating)

    Allowed content types are passed for the same reason. A sub class could
    check these using the ``validated_content_type`` hooks.
    This is mostly useful for file uploads (see ``FileCollection`` or ``FileItem``)
    where you might wish to restrict content types (e.g. images only)
    """
    def __init__(
            self,
            uri_template,
            content_types=('application/json',),
            methods=('get', 'patch', 'put', 'delete', 'post'),
            error_handler=basic_error_handler
    ):
        self._uri = uri_template
        self._content_types = content_types
        self._error_handler = error_handler

        # We dynamically set attributes for the expected
        # falcon HTTP method handlers.
        # This allows the user of ``Resource`` to define a subset
        # of methods to use. E.g. if they dont want to support
        # 'on_post', this would be left off the method list
        for method in methods:
            method_name = 'on_{}'.format(method)
            handler = getattr(self, '_{}'.format(method))
            setattr(self, method_name, handler)

    @property
    def uri_template(self):
        """The URI for this resource
        """
        return self._uri

    @property
    def allowed_content_types(self):
        return self._content_types

    def _post(self, req, resp):
        pass

    def _get(self, req, resp):
        pass

    def _put(self, req, resp):
        pass

    def _patch(self, req, resp):
        pass

    def _delete(self, req, resp):
        pass



class Collection(FeatherResource):
    """Generic class for listing/creating data via a schema

    Using falcons before/after decorators.
    ++++++++++++++++++++++++++++++++++++++

    Remembering that the @ operator is just syntactic sugar,
    if we want to apply a decorator we could do it with minimal effort like this:

        resource = Collection(...)
        resource.on_post = falcon.before(my_function)(resource.on_post)

    Alternatively, we could create a subclass:

        class MyResource(Collection):
            on_post = falcon.before(my_function)(Collection.on_post.__func__)
    """
    def __init__(
            self,
            schema,
            uri_template,
            content_types=('application/json'),
            methods=('get', 'post'),
            error_handler=basic_error_handler
    ):
        super(Collection, self).__init__(
            uri_template,
            content_types,
            methods,
            error_handler
        )
        self._schema = schema

    def _get(self, req, resp):
        """List all schmea objects in the database.

        This method will call ``get_filter`` on the ``MongoSchema`` instance that
        was passed in. The result of ``get_filter`` are then passed to the
        ``find`` method of ``MongoSchema`` in order to retrieve the final
        list of objects to return.
        """
        # dump all schema objects
        cursor = self._schema.find(**self._schema.get_filter(req))
        result = self._schema.dumps(cursor, many=True)
        resp.body = result.data
        resp.content_type = falcon.MEDIA_JSON
        resp.status = falcon.HTTP_OK

    @falcon.before(validate_content_type)
    def _post(self, req, resp):
        """Accepts data passes it to the schema for validation & creation.

        If overriding, note this function uses a decorator to validate the
        content types.
        """
        data = req.bounded_stream.read()
        complete_data, error_dict = self._schema.post(data)
        self._error_handler(error_dict)
        resp.status = falcon.HTTP_CREATED

class Item(FeatherResource):
    """Generic class for getting/editing a single data item via a schema
    """
    def __init__(
            self,
            schema,
            uri_template,
            content_types=('application/json'),
            methods=('get', 'patch', 'put', 'delete')
    ):
        super(Item, self).__init__(uri_template, content_types, methods)
        self._schema = schema

    def _get(self, req, resp, **kwargs):
        """Get a representation of a single object in the schema.

        kwargs contains the lookup parameter specified in the uri template
        (as given by falcon). This will be used to update the result of
        ``get_filter``
        """
        filter_spec = self._schema.get_filter(req)
        try:
            kwargs.update(filter_spec['filter'])
            del filter_spec['filter']
        except KeyError:
            pass
        document = self._schema.get(kwargs, **filter_spec)
        if document:
            result = self._schema.dumps(document)
            resp.body = result.data
            resp.content_type = falcon.MEDIA_JSON
            resp.status = falcon.HTTP_OK
        else:
            raise falcon.HTTPNotFound()

    @falcon.before(validate_content_type)
    def _put(self, req, resp, **kwargs):
        """Replace a schema object with the given data
        """
        data = req.bounded_stream.read()
        validated, error_dict = self._schema.put(kwargs, data)
        self._error_handler(error_dict)
        resp.status = falcon.HTTP_NO_CONTENT
        resp.location = self.uri_template.format(**kwargs)

    @falcon.before(validate_content_type)
    def _patch(self, req, resp, **kwargs):
        """Update an existing schema object with the given data
        """
        data = req.bounded_stream.read()
        validated, error_dict = self._schema.patch(kwargs, data)
        self._error_handler(error_dict)
        resp.status = falcon.HTTP_ACCEPTED
        resp.location = self.uri_template.format(**kwargs)

    def _delete(self, req, resp, **kwargs):
        """Delete an object
        """
        self._schema.delete(kwargs)
        resp.status = falcon.HTTP_NO_CONTENT


class FileCollection(FeatherResource):
    """Collection for posting/listing file uploads.

    By default, all content types are allowed - usually you would want to limit this, e.g. just
    allow images by passing ``('image/png', 'image/jpeg')``
    """
    def __init__(self, store, uri_template='/files', content_types=None, methods=('get', 'post')):
        super(FileCollection, self).__init__(uri_template, content_types, methods)
        self._store = store

    def _get(self, req, resp):
        """Get a list of all file URL's available
        """
        uploads = self._store.list()
        resp.body = simplejson.dumps(uploads)
        resp.status = falcon.HTTP_200

    @falcon.before(validate_content_type)
    def _post(self, req, resp):
        """POST a new file (stream)

        If overriding, note this function uses a decorator to validate the
        content types.
        """
        name = self._store.save(req.stream, req.content_type)
        resp.status = falcon.HTTP_CREATED
        resp.location = "{}/{}".format(self._uri, name)


class FileItem(FeatherResource):
    """Item resource for interacting with single files
    """
    def __init__(self, store, uri_template='/files/{name}', content_types=None, methods=('get',)):
        super(FileItem, self).__init__(uri_template, content_types, methods)
        self._store = store
        self._uri_param = self._uri.split('{')[1].split('}')[0]

    def _get(self, req, resp, **kwargs):
        """Download a single file
        """
        name = kwargs[self._uri_param]
        resp.content_type = mimetypes.guess_type(name)[0]
        resp.stream, resp.stream_len = self._store.open(name)
