from django import forms
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.conf.urls.static import static
import json


class FlowbiteTextInput(forms.widgets.TextInput):
    class Media:
        css = {}
        js = []

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)
        self.attrs.update(
            {
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            }
        )


class FlowbiteNumberInput(forms.widgets.NumberInput):
    class Media:
        css = {}
        js = []

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)
        self.attrs.update(
            {
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            }
        )


class FlowbiteSelectInput(forms.widgets.Select):
    class Media:
        css = {}
        js = []

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)
        self.attrs.update(
            {
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            }
        )


class FlowbiteCheckboxInput(forms.widgets.CheckboxInput):
    class Media:
        css = {}
        js = []

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)
        self.attrs.update(
            {
                "class": "w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
            }
        )


class FlowbiteTextarea(forms.widgets.Textarea):
    class Media:
        css = {}
        js = []

    def __init__(self, attrs=None, options={}):
        self.options = options
        super().__init__(attrs)
        self.attrs.update(
            {
                "class": "block p-2.5 w-full text-sm text-gray-900 bg-gray-50 rounded-lg border border-gray-300 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            }
        )


class FlowbiteImageDropzone(forms.MultiWidget):
    template_name = "django_flowbite_widgets/image_dropzone.html"

    class Media:
        css = {}
        # js = ["django_flowbite_widgets/image_dropzone.js"]
        css = {
            # 'all': ('css/image_url_widget.css',)
        }
        # js = ('js/image_url_widget.js',)


    def __init__(self, attrs=None):
        widgets = [
            forms.ClearableFileInput(attrs={'class': 'flowbite-dropzone-file'}),
            forms.URLInput(attrs={'class': 'flowbite-dropzone-url', 'placeholder': 'Or enter image URL here'})
        ]
        super().__init__(widgets, attrs)


    def decompress(self, value):
        if value:
            # This method will be called with different types of values based on the field
            # If it's a tuple of (file, url), return it
            if isinstance(value, tuple) and len(value) == 2:
                return value
            # For a model instance where the value is already saved
            # This is a placeholder - you'll need to adjust based on your model
            return [None, None]
        return [None, None]


    def no_render(self, name, value, attrs=None, renderer=None):
        """Custom rendering for the widget"""
        if not isinstance(value, list) and value is not None:
            value = self.decompress(value)
        
        output = super().render(name, value, attrs, renderer)
        
        # You could enhance this with custom HTML/JS for the Flowbite dropzone UI
        return f'<div class="flowbite-image-dropzone">{output}<p class="mt-1 text-sm text-gray-500">Upload a file or provide an image URL (one is required)</p></div>'

