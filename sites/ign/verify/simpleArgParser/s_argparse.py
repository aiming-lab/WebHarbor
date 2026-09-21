import argparse
import dataclasses
from dataclasses import fields, MISSING, asdict
from typing import Optional, Union, get_origin, get_args, Type, List
import enum
import json
import sys
import types
import inspect
import re

# Global sentinel for not provided values.
NOT_PROVIDED = object()

class NoMetavarFormatter(argparse.HelpFormatter):
    """Custom formatter that removes metavar display for cleaner help output."""
    
    def _format_action_invocation(self, action):
        if not action.option_strings:
            default = self._get_default_metavar_for_positional(action)
            metavar, = self._metavar_formatter(action, default)(1)
            return metavar
        else:
            parts = []
            # Only add option strings, skip metavar
            if action.option_strings:
                parts.extend(action.option_strings)
            return ', '.join(parts)

class SpecialLoadMarker:
    """Marker class used to denote a field that supports JSON config loading."""
    pass

class PartialDefaults:
    """
    Marker that stores partial default values for a nested dataclass field.
    Use this when you want to provide defaults for some fields of a nested dataclass
    without instantiating it (which would require all required fields).

    Usage:
        @dataclass
        class Outer:
            inner: InnerConfig = partial_defaults(max_tokens=123)
    """
    def __init__(self, **kwargs):
        self.defaults = kwargs

def partial_defaults(**kwargs):
    """
    Create a default for a nested dataclass field that only specifies some fields.
    Fields not listed here remain required and must be provided via CLI.

    Usage:
        @dataclass
        class Outer:
            inner: InnerConfig = partial_defaults(max_tokens=123)
    """
    return PartialDefaults(**kwargs)

def bool_converter(s):
    """Convert string representations to boolean values (case-insensitive: yes/no, true/false)."""
    if isinstance(s, bool):
        return s
    lower = s.lower()
    if lower in ("yes", "true", "t", "y", "1"):
        return True
    elif lower in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError(f"Invalid boolean value: {s}")

def extract_field_comments(cls: Type) -> dict:
    """
    Extract comments above fields and inline comments from the class's source code.
    Returns a dictionary mapping field names to the concatenated comment string.
    Only effective when the source code is accessible.
    """
    try:
        source = inspect.getsource(cls)
    except Exception:
        return {}
    lines = source.splitlines()
    field_pattern = re.compile(r'^\s*(\w+)\s*:')  # matches "field_name :"
    field_help = {}
    current_comments = []
    in_multiline_comment = False
    multiline_buffer = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Handle multiline comments (''' or """)
        if not in_multiline_comment and (stripped.startswith('"""') or stripped.startswith("'''")):
            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                # Single line multiline comment like '''comment'''
                content = stripped[3:-3].strip()
                if content:
                    multiline_buffer.append(content)
            else:
                # Start of multiline comment
                content = stripped[3:].strip()
                if content:
                    multiline_buffer.append(content)
                in_multiline_comment = True
            continue
        
        if in_multiline_comment:
            if stripped.endswith('"""') or stripped.endswith("'''"):
                # End of multiline comment
                content = stripped[:-3].strip()
                if content:
                    multiline_buffer.append(content)
                in_multiline_comment = False
            else:
                # Content inside multiline comment
                if stripped:
                    multiline_buffer.append(stripped)
            continue
        
        # Handle regular comments
        if stripped.startswith('#'):
            comment_text = stripped.lstrip('#').strip()
            current_comments.append(comment_text)
        else:
            # Check if this line contains a field definition
            m = field_pattern.match(line)
            if m:
                field_name = m.group(1)
                all_comments = []
                
                # Add preceding comments
                if current_comments:
                    all_comments.extend(current_comments)
                
                # Add multiline comments
                if multiline_buffer:
                    all_comments.extend(multiline_buffer)
                    multiline_buffer = []
                
                # Check for inline comment
                if '#' in line:
                    comment_start = line.find('#')
                    inline_comment = line[comment_start+1:].strip()
                    if inline_comment:
                        all_comments.append(inline_comment)
                
                if all_comments:
                    field_help[field_name] = " ".join(all_comments)
                
                current_comments = []
            else:
                # Reset comments if we encounter a non-comment, non-field line that's not empty
                if stripped and not stripped.startswith('#'):
                    current_comments = []
                    if multiline_buffer:
                        multiline_buffer = []
    
    return field_help

def extract_enum_comments(cls: Type) -> dict:
    """
    Extract comments above and inline for enum members from the class's source code.
    Returns a dictionary mapping member names to the concatenated comment string.
    Works the same way as extract_field_comments but matches enum assignments (name = value).
    Only effective when the source code is accessible.
    """
    try:
        source = inspect.getsource(cls)
    except Exception:
        return {}
    lines = source.splitlines()
    # Matches enum member assignments like: name = "value" or name = auto()
    member_pattern = re.compile(r'^\s*(\w+)\s*=')
    member_help = {}
    current_comments = []
    in_multiline_comment = False
    multiline_buffer = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Handle multiline comments (''' or """)
        if not in_multiline_comment and (stripped.startswith('"""') or stripped.startswith("'''")):
            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                content = stripped[3:-3].strip()
                if content:
                    multiline_buffer.append(content)
            else:
                content = stripped[3:].strip()
                if content:
                    multiline_buffer.append(content)
                in_multiline_comment = True
            continue

        if in_multiline_comment:
            if stripped.endswith('"""') or stripped.endswith("'''"):
                content = stripped[:-3].strip()
                if content:
                    multiline_buffer.append(content)
                in_multiline_comment = False
            else:
                if stripped:
                    multiline_buffer.append(stripped)
            continue

        # Handle regular comments
        if stripped.startswith('#'):
            comment_text = stripped.lstrip('#').strip()
            current_comments.append(comment_text)
        else:
            m = member_pattern.match(line)
            if m:
                member_name = m.group(1)
                all_comments = []

                if current_comments:
                    all_comments.extend(current_comments)

                if multiline_buffer:
                    all_comments.extend(multiline_buffer)
                    multiline_buffer = []

                # Check for inline comment
                if '#' in line:
                    comment_start = line.find('#')
                    inline_comment = line[comment_start+1:].strip()
                    if inline_comment:
                        all_comments.append(inline_comment)

                if all_comments:
                    member_help[member_name] = " ".join(all_comments)

                current_comments = []
            else:
                if stripped and not stripped.startswith('#'):
                    current_comments = []
                    if multiline_buffer:
                        multiline_buffer = []

    return member_help


def get_by_path(d: dict, path: str):
    """Retrieve a value from a nested dictionary 'd' based on a dot-separated path."""
    parts = path.split('.')
    current = d
    for p in parts:
        if isinstance(current, dict) and p in current:
            current = current[p]
        else:
            return None
    return current

def set_by_path(d: dict, path: str, set_value):
    """Set a value in a nested dictionary 'd' based on a dot-separated path."""
    parts = path.split('.')
    current = d
    for p in parts[:-1]:
        if p not in current or not isinstance(current[p], dict):
            current[p] = {}
        current = current[p]
    # Set the final value
    current[parts[-1]] = set_value
    

def remove_by_path(d: dict, path: str):
    """Remove a key from a nested dictionary 'd' based on a dot-separated path."""
    parts = path.split('.')
    current = d
    for p in parts[:-1]:
        if p in current:
            current = current[p]
        else:
            return
    current.pop(parts[-1], None)

def convert_type(typ: Type, allow_none: bool = False):
    """
    Return a conversion function for the given type.
    For bool type, use the custom bool_converter;
    for Enum types, match based on the enum member name;
    otherwise, return the type itself.
    If allow_none is True, the converter will return None for "none" (case-insensitive).
    """
    base_converter = None
    if typ is bool:
        base_converter = bool_converter
    elif isinstance(typ, type) and issubclass(typ, enum.Enum):
        def enum_converter(s, enum_type=typ):
            try:
                return enum_type[s]
            except KeyError:
                choices = set(member.name for member in enum_type)
                raise KeyError(f"Invalid choice '{s}' for enum {enum_type.__name__}, choices: {choices}") from None
        base_converter = enum_converter
    else:
        base_converter = typ
    
    if allow_none:
        def none_aware_converter(s):
            if isinstance(s, str) and s.strip().lower() == "none":
                return None
            return base_converter(s)
        return none_aware_converter
    return base_converter

def convert_value(value, target_type: Type):
    """
    Convert 'value' to 'target_type'. Supports conversion for bool, Enum, list,
    and basic types. If value is None, returns None.
    """
    if value is None:
        return None

    if get_origin(target_type) in (Union, types.UnionType):
        non_none = [a for a in get_args(target_type) if a is not type(None)]
        if len(non_none) == 1:
            target_type = non_none[0]
    if target_type is bool:
        return bool_converter(value) if isinstance(value, str) else bool(value)
    if isinstance(target_type, type) and issubclass(target_type, enum.Enum):
        if isinstance(value, str):
            return target_type[value]
        return target_type(value)
    if get_origin(target_type) is list:
        inner_type = get_args(target_type)[0]
        # NEW: if the string (after stripping) equals "none" (case-insensitive), return None.
        if isinstance(value, str) and value.strip().lower() == "none":
            return None
        if isinstance(value, str):
            return [convert_value(item.strip(), inner_type) for item in value.split(',')]
        elif isinstance(value, list):
            return [convert_value(item, inner_type) for item in value]
        else:
            raise ValueError(f"Cannot convert {value} to {target_type}")
    try:
        if target_type is str and isinstance(value, str) and value.strip().lower() == "none":
            return None
        return target_type(value)
    except Exception:
        print(f"Error converting value='{value}' to type='{target_type}', thus keep it as type {type(value)}")
        return value

def nest_namespace(ns: dict) -> dict:
    """Convert a flat argparse namespace to a nested dictionary (using dot-separated keys)."""
    nested = {}
    for k, v in ns.items():
        parts = k.split('.')
        current = nested
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = v
    return nested

def deep_merge(a: dict, b: dict) -> dict:
    """
    Recursively merge dictionaries 'a' and 'b'. Values in 'b' override those in 'a',
    except when the value in 'b' is NOT_PROVIDED.
    """
    result = dict(a)
    for k, v in b.items():
        if v is NOT_PROVIDED:
            continue
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def fill_defaults(d: dict, cls: Type) -> dict:
    """
    Fill in missing values in dictionary 'd' using the default values from the dataclass 'cls'.
    If a required field is missing, raise an error.
    """
    result = dict(d)
    for f in fields(cls):
        if f.name not in result or result[f.name] is NOT_PROVIDED:
            # Skip PartialDefaults — they don't provide a full default for the field itself
            if isinstance(f.default, PartialDefaults):
                raise ValueError(f"Missing required parameter: {f.name}")
            elif f.default is MISSING and f.default_factory is MISSING:
                raise ValueError(f"Missing required parameter: {f.name}")
            elif f.default is not MISSING:
                result[f.name] = f.default
            elif f.default_factory is not MISSING:
                result[f.name] = f.default_factory()
        else:
            # If the value is a PartialDefaults, expand it into a dict
            if isinstance(result[f.name], PartialDefaults):
                result[f.name] = dict(result[f.name].defaults)
            if dataclasses.is_dataclass(f.type) and isinstance(result[f.name], dict):
                # Pre-fill missing keys from parent defaults
                defaults_dict = _get_nested_defaults_dict(f)
                if defaults_dict is not None:
                    for key, val in defaults_dict.items():
                        if key not in result[f.name] or result[f.name][key] is NOT_PROVIDED:
                            result[f.name][key] = val
                        elif isinstance(val, PartialDefaults) and isinstance(result[f.name][key], dict):
                            # Nested partial_defaults: pre-fill into the sub-dict
                            for pk, pv in val.defaults.items():
                                if pk not in result[f.name][key] or result[f.name][key][pk] is NOT_PROVIDED:
                                    result[f.name][key][pk] = pv
                result[f.name] = fill_defaults(result[f.name], f.type)
    return result

def _from_dict_internal(cls: Type, d: dict):
    """
    Internal function to construct a dataclass instance from dictionary 'd'. 
    Supports nested dataclasses.
    """
    kwargs = {}
    for f in fields(cls):
        if dataclasses.is_dataclass(f.type):
            sub_dict = d.get(f.name, {})
            kwargs[f.name] = _from_dict_internal(f.type, sub_dict)
        else:
            if f.name in d:
                kwargs[f.name] = convert_value(d[f.name], f.type)
    return cls(**kwargs)

def from_dict(cls: Type, d: dict):
    """
    Construct a dataclass instance from dictionary 'd'. Supports nested dataclasses.
    This is the public API for converting dictionaries to dataclass instances.
    """
    return _from_dict_internal(cls, d)

def collect_field_names(cls: Type, prefix: str = "") -> List[tuple]:
    """
    Recursively collect field names from a dataclass.
    Returns a list of tuples (full_field_name, base_name),
    where full_field_name includes the prefix (e.g. "sampling.gen_n") and base_name is the simple field name (e.g. "gen_n").
    """
    names = []
    for f in fields(cls):
        full_name = f"{prefix}{f.name}"
        if dataclasses.is_dataclass(f.type):
            names.extend(collect_field_names(f.type, prefix=f"{full_name}."))
        else:
            names.append((full_name, f.name))
    return names

def build_alias_map(cls: Type) -> dict:
    """
    Build a global alias map. Traverse all fields (including nested ones) and if a field's base name is unique,
    allow a simplified alias "--<base_name>".
    Returns a dictionary mapping full field names to the simplified option string.
    """
    collected = collect_field_names(cls)
    freq = {}
    for full, base in collected:
        freq[base] = freq.get(base, 0) + 1
    alias_map = {}
    for full, base in collected:
        if freq[base] == 1:
            alias_map[full] = f"--{base}"
    return alias_map

def _get_nested_default_instance(f):
    """If field f has a default that is a dataclass instance (direct or via factory), return it."""
    if f.default is not MISSING and dataclasses.is_dataclass(f.default):
        return f.default
    if f.default_factory is not MISSING:
        try:
            instance = f.default_factory()
            if dataclasses.is_dataclass(instance):
                return instance
        except Exception:
            pass
    return None

def _get_nested_defaults_dict(f):
    """
    Get a dict of default values for a nested dataclass field.
    Supports: dataclass instances (direct or factory), and PartialDefaults markers.
    Returns None if no defaults are available.
    """
    # Check for PartialDefaults marker
    if isinstance(f.default, PartialDefaults):
        return dict(f.default.defaults)
    if f.default_factory is not MISSING:
        try:
            val = f.default_factory()
            if isinstance(val, PartialDefaults):
                return dict(val.defaults)
        except Exception:
            pass
    # Fall back to full dataclass instance
    instance = _get_nested_default_instance(f)
    if instance is not None:
        return {nf.name: getattr(instance, nf.name) for nf in fields(instance)}
    return None

def collect_all_arguments(cls: Type, prefix: str = "", special_fields: set = None, alias_map: dict = None, defaults_override: dict = None):
    """
    Recursively collect all argument information from a dataclass without adding them to parser.
    Returns a list of dictionaries containing argument information for later sorting.
    """
    if special_fields is None:
        special_fields = set()
    if alias_map is None:
        alias_map = {}
    if defaults_override is None:
        defaults_override = {}

    arguments = []
    field_help_map = extract_field_comments(cls)

    for f in fields(cls):
        field_type = f.type
        allow_none = False  # Track if this field allows None (i.e., is Optional/Union with None)
        if get_origin(field_type) in (Union, types.UnionType):
            non_none = [a for a in get_args(field_type) if a is not type(None)]
            if len(non_none) == 1:
                # This is an Optional[X] or X | None type
                allow_none = True
                field_type = non_none[0]
        full_field_name = f"{prefix}{f.name}"

        if dataclasses.is_dataclass(field_type):
            new_prefix = f"{full_field_name}."
            # Determine defaults for nested fields from parent default instance
            nested_defaults = _get_nested_defaults_dict(f) or {}
            # Also check defaults_override from a higher parent
            if not nested_defaults and f.name in defaults_override:
                val = defaults_override[f.name]
                if isinstance(val, PartialDefaults):
                    nested_defaults = dict(val.defaults)
                elif dataclasses.is_dataclass(val):
                    nested_defaults = {nf.name: getattr(val, nf.name) for nf in fields(val)}
                elif isinstance(val, dict):
                    nested_defaults = val
            nested_args = collect_all_arguments(field_type, prefix=new_prefix,
                                              special_fields=special_fields, alias_map=alias_map,
                                              defaults_override=nested_defaults)
            arguments.extend(nested_args)
        else:
            # Build option strings: always include the fully qualified name.
            option_strings = [f"--{full_field_name}"]
            # If alias_map contains a simplified alias, add it but don't duplicate the full name
            if full_field_name in alias_map:
                simplified_alias = alias_map[full_field_name]
                if simplified_alias != f"--{full_field_name}":
                    option_strings.append(simplified_alias)
            
            dest_name = full_field_name
            if get_origin(field_type) is list:
                inner_type = get_args(field_type)[0]
                def list_converter(s, inner_type=inner_type):
                    # NEW: if the input string is "none" (case-insensitive), return None.
                    if s.strip().lower() == "none":
                        return None
                    # If the input string is empty, return an empty list.
                    if len(s) == 0:
                        return []
                    return [convert_value(item.strip(), inner_type) for item in s.split(',')]
                conv_type = list_converter
            else:
                conv_type = convert_type(field_type, allow_none=allow_none)
            
            # Build help text: type and default first, then comments
            # Use original f.type for display so Optional/Union types show fully (e.g., "str | None")
            type_str = str(f.type).replace("<class '", "").replace("'>", "").replace("<enum '", "").replace("'>", "")
            help_parts = [f"(type: {type_str})"]
            
            # Add choices for enum types
            if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
                choices_str = "{" + ",".join([choice.name for choice in field_type]) + "}"
                help_parts.append(f"(choices: {choices_str})")
            
            # Check if this is a required field
            is_required = f.default is MISSING and f.default_factory is MISSING

            # Check if parent provides a default for this field
            parent_default = defaults_override.get(f.name, MISSING)

            # Add default value info
            # Parent override takes priority over field's own default
            if parent_default is not MISSING:
                is_required = False
                default_val = parent_default
                if isinstance(default_val, enum.Enum):
                    help_parts.append(f"(default: {default_val.name})")
                else:
                    help_parts.append(f"(default: {default_val})")
            elif is_required:
                help_parts.append("(required)")
            else:
                default_val = f.default if f.default is not MISSING else f.default_factory()
                if isinstance(default_val, SpecialLoadMarker):
                    help_parts.append("(JSON config file path)")
                elif isinstance(default_val, enum.Enum):
                    help_parts.append(f"(default: {default_val.name})")
                else:
                    help_parts.append(f"(default: {default_val})")
            
            # Add comments at the end if they exist
            extra_help = field_help_map.get(f.name, "")
            if extra_help:
                help_parts.append(extra_help)
            
            help_text = " ".join(help_parts)
            # Escape % characters to prevent argparse formatting errors
            help_text = help_text.replace("%", "%%")
            
            kwargs = {
                "dest": dest_name,
                "type": conv_type,
                "help": help_text
            }
            if isinstance(field_type, type) and issubclass(field_type, enum.Enum):
                kwargs["choices"] = list(field_type)
            
            # If the field's default value is special_load() (a SpecialLoadMarker instance), record its path.
            if isinstance(f.default, SpecialLoadMarker):
                if field_type is not str:
                    raise TypeError(
                        f"SpecialLoadMarker field '{full_field_name}' must be typed as str or str | None, got {field_type}"
                    )
                special_fields.add(full_field_name)
                if len(special_fields) > 1:
                    raise ValueError(f"At most one SpecialLoadMarker field is allowed, found: {special_fields}")
            
            kwargs["default"] = NOT_PROVIDED
            
            # Store argument information for sorting
            arguments.append({
                "option_strings": option_strings,
                "kwargs": kwargs,
                "full_field_name": full_field_name,
                "is_required": is_required,
                "separator_count": full_field_name.count('.'),
                "primary_name": option_strings[0]  # For sorting
            })
    
    return arguments

def add_arguments_from_dataclass(parser: argparse.ArgumentParser, cls: Type, prefix: str = "",
                                 special_fields: set = None, alias_map: dict = None,
                                 defaults_override: dict = None):
    """
    Recursively add command-line arguments based on the dataclass definition with custom ordering:
    1. Required arguments first
    2. Then by separator depth (fewer separators first)
    3. Then alphabetically by primary option name
    """
    if special_fields is None:
        special_fields = set()
    if alias_map is None:
        alias_map = {}

    # Collect all arguments
    all_arguments = collect_all_arguments(cls, prefix, special_fields, alias_map, defaults_override)
    
    # Sort arguments according to the requirements:
    # 1. Required args first (is_required=True comes before is_required=False)
    # 2. Fewer separators first (lower separator_count comes first)  
    # 3. Alphabetically by primary option name
    all_arguments.sort(key=lambda arg: (
        not arg["is_required"],  # Required first (False < True, so required comes first)
        arg["separator_count"],   # Fewer separators first
        arg["primary_name"]       # Alphabetically
    ))
    
    # Add arguments to parser in sorted order
    for arg_info in all_arguments:
        parser.add_argument(*arg_info["option_strings"], **arg_info["kwargs"])

def recursive_process(obj):
    """
    Recursively call the pre_process and post_process methods of a dataclass object.
    Processing order:
    1. Call pre_process() on the current object
    2. Recursively process all nested dataclass fields
    3. Call post_process() on the current object
    """
    if dataclasses.is_dataclass(obj):
        # Step 1: Call pre_process if it exists
        if hasattr(obj, "pre_process") and callable(obj.pre_process):
            obj.pre_process()
        
        # Step 2: Recursively process nested dataclass fields
        for field in fields(obj):
            value = getattr(obj, field.name)
            if dataclasses.is_dataclass(value):
                recursive_process(value)
        
        # Step 3: Call post_process if it exists
        if hasattr(obj, "post_process") and callable(obj.post_process):
            obj.post_process()

def _validate_json_keys(json_dict: dict, cls: Type, prefix: str = ""):
    """
    Recursively validate that all keys in json_dict correspond to fields in the dataclass cls.
    Raises ValueError if unknown keys are found.
    """
    field_names = {f.name for f in fields(cls)}
    field_map = {f.name: f for f in fields(cls)}
    unknown = [f"{prefix}{k}" for k in json_dict if k not in field_names]
    if unknown:
        raise ValueError(f"Unknown fields in JSON config: {unknown}")
    for k, v in json_dict.items():
        if isinstance(v, dict) and k in field_map:
            ft = field_map[k].type
            if get_origin(ft) in (Union, types.UnionType):
                non_none = [a for a in get_args(ft) if a is not type(None)]
                if len(non_none) == 1:
                    ft = non_none[0]
            if dataclasses.is_dataclass(ft):
                _validate_json_keys(v, ft, prefix=f"{prefix}{k}.")

def _finalize_parsed_args(cls: Type, flat_ns: dict, special_fields: set):
    """
    Shared post-parse finalization logic:
      - Nest the flat namespace into a nested dict
      - Handle SpecialLoadMarker fields (JSON config loading)
      - Fill defaults and check required fields
      - Convert to dataclass instance via from_dict
      - Run recursive pre/post processing
    Returns the final dataclass instance.
    """
    nested_args = nest_namespace(flat_ns)

    if special_fields:
        special_field_path = next(iter(special_fields))
        special_value = get_by_path(nested_args, special_field_path)
        if isinstance(special_value, str) and special_value.strip() and special_value.strip().lower() == "none":
            special_value = None
            set_by_path(nested_args, special_field_path, None)

        if isinstance(special_value, str) and special_value.strip():
            with open(special_value, 'r') as f:
                json_special = json.load(f)
            # Keep the path of the loaded config file
            set_by_path(nested_args, special_field_path, special_value)
            _validate_json_keys(json_special, cls)
            nested_args = deep_merge(json_special, nested_args)
        elif special_value is NOT_PROVIDED:
            # If not provided via command line, set it to None so it doesn't hold the marker instance
            set_by_path(nested_args, special_field_path, None)

    final_dict = fill_defaults(nested_args, cls)
    config = from_dict(cls, final_dict)
    recursive_process(config)
    return config


def parse_args(cls: Type, pass_in: List[str] = None, disable_cmd: bool = False):
    """
    Parse command-line arguments, supporting:
      - Merging code-provided arguments (pass_in) with sys.argv (command-line arguments take priority);
      - JSON configuration file loading: if a field's default value is special_load() (i.e. a SpecialLoadMarker instance)
        and the user provides a non-empty string, then load that string as a JSON file and merge its configuration.
      - Merging default values (and checking required fields);
      - Recursively calling post-processing methods (process_args/post_process) for all dataclasses;
      - If --help/-h is detected, print the help information and exit.
    Priority: command line > code input > specially loaded JSON config > default values.
    disable_cmd: whether disable parsing the args by the command line
    """
    code_args = pass_in if pass_in is not None else []
    cmd_args = sys.argv[1:] if not disable_cmd else []
    args_list = code_args + cmd_args

    if any(arg in ('-h', '--help') for arg in args_list):
        full_parser = argparse.ArgumentParser(formatter_class=NoMetavarFormatter)
        alias_map = build_alias_map(cls)
        add_arguments_from_dataclass(full_parser, cls, alias_map=alias_map)
        full_parser.print_help()
        sys.exit(0)

    special_fields = set()
    alias_map = build_alias_map(cls)
    parser = argparse.ArgumentParser(formatter_class=NoMetavarFormatter)
    add_arguments_from_dataclass(parser, cls, special_fields=special_fields, alias_map=alias_map)
    args = parser.parse_args(args_list)
    flat_ns = vars(args)

    try:
        return _finalize_parsed_args(cls, flat_ns, special_fields)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
        parser.error(str(e))

def _collect_tree_lines(group_dict: dict, max_depth: int, current_depth: int = 0) -> List[tuple]:
    """
    Recursively collect (indent_prefix, name, description) tuples for the command tree.
    Each entry also carries structural info for drawing ASCII tree connectors.
    Returns a flat list of (depth, name, desc, is_group) tuples.
    """
    lines = []
    enum_comments = {}
    seen_types = set()
    for key in group_dict:
        if isinstance(key, enum.Enum) and type(key) not in seen_types:
            seen_types.add(type(key))
            enum_comments.update(extract_enum_comments(type(key)))

    items = list(group_dict.items())
    for i, (key, value) in enumerate(items):
        name = key.name if isinstance(key, enum.Enum) else str(key)
        desc = enum_comments.get(name, "")
        is_group = isinstance(value, dict)
        lines.append((current_depth, name, desc, is_group))
        # Recurse into sub-groups if within depth limit
        if is_group and current_depth + 1 < max_depth:
            sub_lines = _collect_tree_lines(value, max_depth, current_depth + 1)
            lines.extend(sub_lines)
    return lines


def _render_tree(lines: List[tuple]) -> List[str]:
    """
    Render collected tree lines with ASCII box-drawing connectors.
    Input: list of (depth, name, desc, is_group) tuples.
    Output: list of formatted strings ready to print.
    """
    if not lines:
        return []

    # Track parent indices at each depth to know which are "last child"
    # We process in order and use a stack to draw vertical lines
    result = []
    # For each depth, track whether the most recent item at that depth is the last sibling
    # We need to know siblings: items at the same depth with the same parent
    # Simple approach: walk through and compute connectors

    # Group items by their parent context
    # We'll track a stack of "has more siblings" booleans
    stack = []  # stack[d] = True if there are more siblings at depth d

    for idx, (depth, name, desc, is_group) in enumerate(lines):
        # Trim stack to current depth
        while len(stack) > depth:
            stack.pop()

        # Determine if this is the last sibling at this depth
        is_last = True
        for j in range(idx + 1, len(lines)):
            if lines[j][0] < depth:
                break
            if lines[j][0] == depth:
                is_last = False
                break

        # Build prefix from stack
        prefix_parts = []
        for d in range(len(stack)):
            if stack[d]:
                prefix_parts.append("│   ")
            else:
                prefix_parts.append("    ")

        # Add connector for this item
        if depth == 0:
            connector = ""
        elif is_last:
            connector = "└── "
        else:
            connector = "├── "

        prefix = "".join(prefix_parts) + connector

        # Build the line
        line = f"  {prefix}{name}"
        if desc:
            line += f"  ({desc})"

        result.append(line)

        # Update stack for children
        if len(stack) <= depth:
            stack.append(not is_last)
        else:
            stack[depth] = not is_last

    return result


def _print_command_group_help(group_dict: dict, command_path_parts: List[str],
                              description: str = "", max_depth: int = 2):
    """
    Print help for a command group (non-leaf level) showing available subcommands
    as an ASCII tree up to max_depth levels deep.
    Extracts comments from enum source code to display as command descriptions.
    """
    prog = sys.argv[0] if sys.argv else "program"
    path_str = " ".join(command_path_parts)
    if path_str:
        print(f"usage: {prog} {path_str} <command> [options]")
    else:
        if description:
            print(description)
            print()
        print(f"usage: {prog} <command> [options]")
    print()

    tree_lines = _collect_tree_lines(group_dict, max_depth)
    rendered = _render_tree(tree_lines)

    print("Available commands:")
    for line in rendered:
        print(line)
    print()


def parse_args_with_commands(
    commands: dict,
    description: str = "",
    pass_in: List[str] = None,
    disable_cmd: bool = False,
    max_depth: int = 2,
) -> tuple:
    """
    Parse command-line arguments with nested subcommand support.

    The 'commands' dict uses enum members as keys at every level.
    Dict values are either:
      - A dataclass type (leaf command)
      - Another dict (command group, for nesting)

    Returns a tuple (command_tuple, config_instance) where:
      - command_tuple is a tuple of enum members representing the command path
        (e.g., (TopCommand.model, ModelCommand.train))
      - config_instance is the parsed dataclass instance for the leaf command

    All existing features work per-leaf-command: nested dataclass fields, enums,
    bools, lists, Optional types, SpecialLoadMarker, aliases, pre/post processing.

    Args:
        commands: Nested dict mapping enum members to dataclass types or sub-dicts.
        description: Optional description shown in top-level help.
        pass_in: Optional list of argument strings (merged with sys.argv).
        disable_cmd: If True, ignore sys.argv and only use pass_in.
        max_depth: Max depth of subcommands to show in help output (default: 2).
    """
    code_args = pass_in if pass_in is not None else []
    cmd_args = sys.argv[1:] if not disable_cmd else []
    args_list = code_args + cmd_args

    # Walk the command tree, consuming positional tokens from the left
    current = commands
    command_parts = []      # enum members collected along the path
    command_names = []      # string names for help display
    remaining = list(args_list)

    while isinstance(current, dict):
        # Build name-to-enum lookup for this level
        name_to_enum = {}
        for key in current:
            name = key.name if isinstance(key, enum.Enum) else str(key)
            name_to_enum[name] = key

        # No more tokens or next token is a flag
        if not remaining or remaining[0].startswith('-'):
            # Check for help
            if remaining and remaining[0] in ('-h', '--help'):
                _print_command_group_help(current, command_names, description, max_depth=max_depth)
                sys.exit(0)
            # No command specified -- show help and exit with error
            _print_command_group_help(current, command_names, description, max_depth=max_depth)
            print("Error: no command specified.", file=sys.stderr)
            sys.exit(2)

        token = remaining.pop(0)

        if token in name_to_enum:
            enum_member = name_to_enum[token]
            command_parts.append(enum_member)
            command_names.append(token)
            current = current[enum_member]
        else:
            # Check if it's a help flag that came without being caught above
            if token in ('-h', '--help'):
                _print_command_group_help(current, command_names, description, max_depth=max_depth)
                sys.exit(0)
            # Unknown command
            _print_command_group_help(current, command_names, description, max_depth=max_depth)
            print(f"Error: unknown command '{token}'.", file=sys.stderr)
            sys.exit(2)

    # 'current' is now the leaf dataclass type
    cls = current

    # Check for help in remaining args at the leaf level
    if any(arg in ('-h', '--help') for arg in remaining):
        leaf_parser = argparse.ArgumentParser(
            prog=" ".join([sys.argv[0] if sys.argv else "program"] + command_names),
            formatter_class=NoMetavarFormatter,
        )
        alias_map = build_alias_map(cls)
        add_arguments_from_dataclass(leaf_parser, cls, alias_map=alias_map)
        leaf_parser.print_help()
        sys.exit(0)

    # Parse remaining args with argparse for the leaf dataclass
    special_fields = set()
    alias_map = build_alias_map(cls)
    parser = argparse.ArgumentParser(
        prog=" ".join([sys.argv[0] if sys.argv else "program"] + command_names),
        formatter_class=NoMetavarFormatter,
    )
    add_arguments_from_dataclass(parser, cls, special_fields=special_fields, alias_map=alias_map)
    args = parser.parse_args(remaining)
    flat_ns = vars(args)

    try:
        config = _finalize_parsed_args(cls, flat_ns, special_fields)
    except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
        parser.error(str(e))
    return tuple(command_parts), config


def to_json(config) -> str:
    """
    Convert a dataclass instance to a JSON string.
    Enum types are converted to their names.
    """
    def default(o):
        if isinstance(o, enum.Enum):
            return o.name
        if isinstance(o, SpecialLoadMarker):
            return None
        raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")
    return json.dumps(asdict(config), indent=4, default=default)

def to_dict(config) -> dict:
    """
    Convert a dataclass instance to a dictionary.
    Supports nested dataclasses. Enum types are converted to their names.
    """
    def convert(obj):
        if isinstance(obj, enum.Enum):
            return obj.name
        if isinstance(obj, SpecialLoadMarker):
            return None
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {f.name: convert(getattr(obj, f.name)) for f in fields(obj)}
        if isinstance(obj, list):
            return [convert(item) for item in obj]
        if isinstance(obj, dict):
            return {k: convert(v) for k, v in obj.items()}
        return obj
    return convert(config)

def from_json(cls: Type, path: str) -> object:
    """
    Load a JSON file and construct a dataclass instance.
    Supports nested dataclasses.
    """
    with open(path, 'r') as f:
        data = json.load(f)
    return _from_dict_internal(cls, data)

def main():
    print("simpleArgParser: Please use parse_args() in your code to parse configuration.")

if __name__ == "__main__":
    main()
