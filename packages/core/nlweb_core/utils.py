# Copyright (c) 2025 Microsoft Corporation.
# Licensed under the MIT License

"""
Common utility functions used across NLWeb.
"""

import json
from typing import Any, Dict, List, Union


def get_param(query_params, param_name, param_type=str, default_value=None):
    """
    Get a parameter from query_params with type conversion.

    Args:
        query_params: Dictionary of query parameters
        param_name: Name of the parameter to retrieve
        param_type: Type to convert the parameter to (str, int, float, bool, list)
        default_value: Default value if parameter not found

    Returns:
        The parameter value converted to the specified type, or default_value
    """
    value = query_params.get(param_name, default_value)
    if (value is not None):
        if param_type == str:
            if isinstance(value, list):
                return value[0] if value else ""
            return value
        elif param_type == int:
            return int(value)
        elif param_type == float:
            return float(value)
        elif param_type == bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, list):
                return value[0].lower() == "true"
            return value.lower() == "true"
        elif param_type == list:
            if isinstance(value, list):
                return value
            return [item.strip() for item in value.strip('[]').split(',') if item.strip()]
        else:
            raise ValueError(f"Unsupported parameter type: {param_type}")
    return default_value


def jsonify(obj):
    """Convert a string to JSON object if it's a JSON string, otherwise return as-is."""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except json.JSONDecodeError:
            return obj
    return obj


def trim_json(obj):
    """
    Trim JSON object based on its @type, removing unnecessary fields.

    Args:
        obj: JSON object (dict) or JSON string to trim

    Returns:
        Trimmed JSON object
    """
    obj = jsonify(obj)
    objType = obj["@type"] if "@type" in obj else ["Thing"]
    if not isinstance(objType, list):
        objType = [objType]
    if (objType == ["Thing"]):
        return obj
    if ("Recipe" in objType):
        return _trim_recipe(obj)
    if ("Movie" in objType or "TVSeries" in objType):
        return _trim_movie(obj)
    return obj


def _collateObjAttr(obj):
    """Collate object attributes into lists."""
    items = {}
    for attr in obj.keys():
        if (attr in items):
            items[attr].append(obj[attr])
        else:
            items[attr] = [obj[attr]]
    return items


def _trim_recipe(obj):
    """Trim Recipe objects, removing publisher, images, etc."""
    obj = jsonify(obj)
    items = _collateObjAttr(obj)
    js = {}
    skipAttrs = ["mainEntityOfPage", "publisher", "image", "datePublished", "dateModified",
                 "author"]
    for attr in items.keys():
        if (attr in skipAttrs):
            continue
        js[attr] = items[attr]
    return js


def _trim_movie(obj, hard=False):
    """Trim Movie/TVSeries objects, removing publisher, images, etc."""
    items = _collateObjAttr(obj)
    js = {}
    skipAttrs = ["mainEntityOfPage", "publisher", "image", "datePublished", "dateModified", "author", "trailer"]
    if (hard):
        skipAttrs.extend(["actor", "director", "creator", "review"])
    for attr in items.keys():
        if (attr in skipAttrs):
            continue
        elif (attr == "actor" or attr == "director" or attr == "creator"):
            if ("name" in items[attr]):
                if (attr not in js):
                    js[attr] = []
                js[attr].append(items[attr]["name"])
        elif (attr == "review"):
            items['review'] = []
            for review in items['review']:
                if ("reviewBody" in review):
                    js[attr].append(review["reviewBody"])
        else:
            js[attr] = items[attr]
    return js


def fill_prompt_variables(prompt_str, *param_dicts):
    """
    Substitute variables in the prompt string with values from one or more param dicts.

    Variables in the prompt are in the format {variable.attribute} or {variable}.
    For example: {request.site}, {site.itemType}, {item.description}

    Args:
        prompt_str: The prompt string with variables to substitute
        *param_dicts: One or more dicts of parameters to substitute. Later dicts override earlier ones.
                      (e.g., {'request.site': 'example.com'}, {'item.description': 'text'})

    Returns:
        The prompt string with variables substituted
    """
    if not param_dicts:
        return prompt_str

    # Iterate through all provided dicts
    for params in param_dicts:
        if params:
            for key, value in params.items():
                placeholder = '{' + key + '}'
                # Ensure value is a string
                if not isinstance(value, str):
                    value = str(value)
                prompt_str = prompt_str.replace(placeholder, value)

    return prompt_str
