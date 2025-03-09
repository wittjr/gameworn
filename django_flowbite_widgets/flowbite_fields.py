from django import forms
from .flowbite_widgets import FlowbiteImageDropzone
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

class FlowbiteImageDropzoneField(forms.MultiValueField):
    widget = FlowbiteImageDropzone

    # def __init__(self, max_file_size=5242880, allowed_extensions=None, **kwargs):
    #     # Required is handled specially since we need at least one of the two subfields
    #     required = kwargs.pop('required', True)
        
    #     # Create the subfields
    #     fields = (
    #         forms.ImageField(
    #             required=False,
    #             # validators=[
    #             #     self._file_size_validator(max_file_size),
    #             #     self._file_extension_validator(allowed_extensions or ['jpg', 'jpeg', 'png', 'gif', 'webp'])
    #             # ]
    #         ),
    #         forms.URLField(required=False)
    #     )
        
    #     # Initialize with both fields required=False, but handle our own required logic
    #     super().__init__(fields=fields, require_all_fields=False, required=required, **kwargs)

    
    def __init__(self, file_field_name='image', url_field_name='image_url', **kwargs):
        self.file_field_name = file_field_name
        self.url_field_name = url_field_name
        
        # Define the fields
        fields = (
            forms.ImageField(required=False),
            forms.URLField(required=False)
        )
        
        # Make the overall field not required by default
        # We'll handle our own validation to ensure at least one is provided
        kwargs.setdefault('require_all_fields', False)
        kwargs.setdefault('required', False)
        
        super().__init__(fields, **kwargs)


    def compress(self, data_list):
        if not data_list:
            return None
        
        file_value = data_list[0] if data_list[0] else None
        url_value = data_list[1] if data_list[1] else None
        
        return (file_value, url_value)
    
    def clean(self, value):
        file_value, url_value = value[0], value[1]
        
        if not file_value and not url_value:
            raise ValidationError(
                _('Please provide either an image file or an image URL.'),
                code='required'
            )
        
        # Call parent's clean method to validate individual fields
        return super().clean(value)


class FlowbiteImageDropzoneFormField(FlowbiteImageDropzoneField):
    """
    A custom form field for use with FlowbiteImageDropzoneField model field.
    """
    pass


class FlowbiteImageDropzoneModelField(models.Field):
    """
    A model field that stores either an image file or a URL to an image,
    using two separate database fields.
    """
    
    description = _("Image from file or URL")
    
    def __init__(self, file_field_name='image', url_field_name='image_url', **kwargs):
        self.file_field_name = file_field_name
        self.url_field_name = url_field_name
        kwargs['editable'] = True
        super().__init__(**kwargs)
    
    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs['file_field_name'] = self.file_field_name
        kwargs['url_field_name'] = self.url_field_name
        return name, path, args, kwargs
    
    def formfield(self, **kwargs):
        defaults = {
            'form_class': FlowbiteImageDropzoneFormField,
            'file_field_name': self.file_field_name,
            'url_field_name': self.url_field_name,
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)
    
    def contribute_to_class(self, cls, name, **kwargs):
        """
        This field doesn't actually create a database column.
        Instead, it relies on the two fields specified by file_field_name
        and url_field_name.
        """
        super().contribute_to_class(cls, name, **kwargs)
        
        # Add a descriptor to handle getting/setting the values
        setattr(cls, name, FlowbiteImageDropzoneDescriptor(self))
    
    def get_prep_value(self, value):
        """
        Prepare the value for the database.
        This field doesn't actually store anything directly.
        """
        return None
    
    def db_type(self, connection):
        """
        This field doesn't have a database representation.
        """
        return None


class FlowbiteImageDropzoneDescriptor:
    """
    Descriptor for handling the getting and setting of the composite field value.
    """
    
    def __init__(self, field):
        self.field = field
        self.file_field_name = field.file_field_name
        self.url_field_name = field.url_field_name
    
    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        
        # Get the values from the actual fields
        file_value = getattr(instance, self.file_field_name, None)
        url_value = getattr(instance, self.url_field_name, None)
        
        return (file_value, url_value)
    
    def __set__(self, instance, value):
        if value is None:
            setattr(instance, self.file_field_name, None)
            setattr(instance, self.url_field_name, None)
            return
        
        # If it's coming from the form, it will be a tuple of (file, url)
        if isinstance(value, tuple) and len(value) == 2:
            file_value, url_value = value
            setattr(instance, self.file_field_name, file_value)
            setattr(instance, self.url_field_name, url_value)
        else:
            # Handle other cases as needed
            pass
