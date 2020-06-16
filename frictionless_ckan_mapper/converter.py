'''Functions for converting between CKAN's dataset and Data Packages.
'''
import re
import json

import six
import slugify


def _convert_to_datapackage_resource(resource_dict):
    '''Convert a CKAN resource dict into a Data Package resource dict.

    '''
    resource = {}

    if resource_dict.get('url'):
        resource['path'] = resource_dict['url']
    # TODO: DataStore only resources?

    if resource_dict.get('description'):
        resource['description'] = resource_dict['description']

    if resource_dict.get('format'):
        resource['format'] = resource_dict['format']

    if resource_dict.get('hash'):
        resource['hash'] = resource_dict['hash']

    if resource_dict.get('name'):
        resource['name'] = slugify.slugify(resource_dict['name']).lower()
        resource['title'] = resource_dict['name']
    else:
        resource['name'] = resource_dict['id']

    schema = resource_dict.get('schema')
    if isinstance(schema, six.string_types):
        try:
            resource['schema'] = json.loads(schema)
        except ValueError:
            # Assume it's a path or URL
            resource['schema'] = schema
    elif isinstance(schema, dict):
        resource['schema'] = schema

    return resource


def dataset_to_datapackage(dataset_dict):
    '''Convert the given CKAN dataset dict into a Data Package dict.

    :returns: the datapackage dict
    :rtype: dict

    '''
    parsers = [
        _rename_dict_key('title', 'title'),
        _rename_dict_key('version', 'version'),
        _parse_ckan_url,
        _parse_notes,
        _parse_license,
        _parse_author_and_source,
        _parse_maintainer,
        _parse_tags,
        _parse_extras,
    ]
    datapackage = {
        'name': dataset_dict['name']
    }

    for parser in parsers:
        datapackage.update(parser(dataset_dict))

    resources = dataset_dict.get('resources')
    if resources:
        datapackage['resources'] = [_convert_to_datapackage_resource(r)
                                    for r in resources]

    # Ensure unique resource names
    names = {}
    for resource in datapackage.get('resources', []):
        if resource['name'] in names.keys():
            old_resource_name = resource['name']
            resource['name'] = resource['name'] + str(names[old_resource_name])
            names[old_resource_name] += 1
        else:
            names[resource['name']] = 0

    return datapackage


def datapackage_to_dataset(datapackage):
    '''Convert the given datapackage into a CKAN dataset dict.

    :returns: the dataset dict
    :rtype: dict
    '''
    parsers = [
        _rename_dict_key('title', 'title'),
        _rename_dict_key('version', 'version'),
        _rename_dict_key('description', 'notes'),
        _datapackage_parse_license,
        _datapackage_parse_sources,
        _datapackage_parse_author,
        _datapackage_parse_keywords,
        _datapackage_parse_unknown_fields_as_extras,
    ]
    dataset_dict = {
        'name': datapackage.descriptor['name'].lower()
    }

    for parser in parsers:
        dataset_dict.update(parser(datapackage.descriptor))

    if datapackage.resources:
        dataset_dict['resources'] = [_datapackage_resource_to_ckan_resource(r)
                                     for r in datapackage.resources]

    return dataset_dict


def _datapackage_resource_to_ckan_resource(resource):
    resource_dict = {}

    if resource.descriptor.get('name'):
        name = resource.descriptor.get('title') or resource.descriptor['name']
        resource_dict['name'] = name

    if resource.local:
        resource_dict['path'] = resource.source
    elif resource.remote:
        resource_dict['url'] = resource.source
    elif resource.inline:
        resource_dict['data'] = resource.source
    else:
        raise NotImplementedError('Multipart resources not yet supported')

    if resource.descriptor.get('description'):
        resource_dict['description'] = resource.descriptor['description']

    if resource.descriptor.get('format'):
        resource_dict['format'] = resource.descriptor['format']

    if resource.descriptor.get('hash'):
        resource_dict['hash'] = resource.descriptor['hash']

    if resource.descriptor.get('schema'):
        resource_dict['schema'] = resource.descriptor['schema']

    return resource_dict


def _rename_dict_key(original_key, destination_key):
    def _parser(the_dict):
        result = {}

        if the_dict.get(original_key):
            result[destination_key] = the_dict[original_key]

        return result
    return _parser


def _parse_ckan_url(dataset_dict):
    result = {}

    if dataset_dict.get('ckan_url'):
        result['homepage'] = dataset_dict['ckan_url']

    return result


def _parse_notes(dataset_dict):
    result = {}

    if dataset_dict.get('notes'):
        result['description'] = dataset_dict['notes']

    return result


def _parse_license(dataset_dict):
    result = {}
    dataset_license = {}

    if dataset_dict.get('license_id'):
        dataset_license['type'] = dataset_dict['license_id']
    if dataset_dict.get('license_title'):
        dataset_license['title'] = dataset_dict['license_title']
    if dataset_dict.get('license_url'):
        dataset_license['url'] = dataset_dict['license_url']

    if dataset_license:
        result['license'] = dataset_license

    return result


def _parse_author_and_source(dataset_dict):
    result = {}
    source = {}

    if dataset_dict.get('author'):
        source['name'] = dataset_dict['author']
    if dataset_dict.get('author_email'):
        source['email'] = dataset_dict['author_email']
    if dataset_dict.get('url'):
        source['web'] = dataset_dict['url']

    if source:
        result['sources'] = [source]

    return result


def _parse_maintainer(dataset_dict):
    result = {}
    author = {}

    if dataset_dict.get('maintainer'):
        author['name'] = dataset_dict['maintainer']
    if dataset_dict.get('maintainer_email'):
        author['email'] = dataset_dict['maintainer_email']

    if author:
        result['author'] = author

    return result


def _parse_tags(dataset_dict):
    result = {}

    keywords = [tag['name'] for tag in dataset_dict.get('tags', [])]

    if keywords:
        result['keywords'] = keywords

    return result


def _parse_extras(dataset_dict):
    result = {}

    extras = [[extra['key'], extra['value']] for extra
              in dataset_dict.get('extras', [])]

    for extra in extras:
        try:
            extra[1] = json.loads(extra[1])
        except (ValueError, TypeError):
            pass

    if extras:
        result['extras'] = dict(extras)

    return result


def _datapackage_parse_license(datapackage_dict):
    result = {}

    dataset_license = datapackage_dict.get('license')
    if dataset_license:
        if isinstance(dataset_license, dict):
            if dataset_license.get('type'):
                result['license_id'] = dataset_license['type']
            if dataset_license.get('title'):
                result['license_title'] = dataset_license['title']
            if dataset_license.get('title'):
                result['license_url'] = dataset_license['url']
        elif isinstance(dataset_license, six.string_types):
            result['license_id'] = dataset_license

    return result


def _datapackage_parse_sources(datapackage_dict):
    result = {}

    sources = datapackage_dict.get('sources')
    if sources:
        author = sources[0].get('name')
        author_email = sources[0].get('email')
        source = sources[0].get('web')
        if author:
            result['author'] = author
        if author_email:
            result['author_email'] = author_email
        if source:
            result['url'] = source

    return result


def _datapackage_parse_author(datapackage_dict):
    result = {}

    author = datapackage_dict.get('author')
    if author:
        maintainer = maintainer_email = None

        if isinstance(author, dict):
            maintainer = author.get('name')
            maintainer_email = author.get('email')
        elif isinstance(author, six.string_types):
            match = re.match(r'(?P<name>[^<]+)'
                             r'(?:<(?P<email>\S+)>)?',
                             author)

            maintainer = match.group('name')
            maintainer_email = match.group('email')

        if maintainer:
            result['maintainer'] = maintainer.strip()
        if maintainer_email:
            result['maintainer_email'] = maintainer_email

    return result


def _datapackage_parse_keywords(datapackage_dict):
    result = {}

    keywords = datapackage_dict.get('keywords')
    if keywords:
        result['tags'] = [{'name': slugify.slugify(keyword)}
                          for keyword in keywords]

    return result


def _datapackage_parse_unknown_fields_as_extras(datapackage_dict):
    # FIXME: It's bad to hardcode it here. Instead, we should change the
    # parsers pattern to remove whatever they use from the `datapackage_dict`
    # and call this parser at last. Anything that's still in `datapackage_dict`
    # would then be added to extras.
    known_fields = [
        'name',
        'resources',
        'license',
        'title',
        'description',
        'homepage',
        'version',
        'sources',
        'author',
        'keywords',
    ]

    result = {}
    extras = [{'key': k, 'value': v}
              for k, v in datapackage_dict.items()
              if k not in known_fields]

    if extras:
        for extra in extras:
            value = extra['value']
            if isinstance(value, (dict, list)):
                extra['value'] = json.dumps(value)
        result['extras'] = extras

    return result
